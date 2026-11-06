"""
MongoDB repository implementation replicating store/mongo.
Supports MongoDB Atlas and local MongoDB with proper index migrations,
partial unique idempotency indexing, and transaction-safe semantics.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import pymongo
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.config.logging import logger
from app.core.entity import utc_now
from app.core.exceptions import (
    ErrAlreadyExists,
    ErrPlanNotFound,
    ErrFeatureNotFound,
    ErrSubscriptionNotFound,
    ErrSubscriptionCanceled,
    ErrSubscriptionExpired,
    ErrCouponNotFound,
    ErrCouponDepleted,
    ErrInvoiceNotFound,
    ErrUnavailable,
)
from app.models.plan import Plan, PlanStatus, Period
from app.models.feature import CatalogFeature
from app.models.subscription import Subscription, SubscriptionStatus, Resume
from app.models.meter import UsageEvent
from app.models.entitlement import EntitlementResult
from app.models.invoice import Invoice, InvoiceStatus
from app.models.coupon import Coupon, CouponApplication
from app.models.student import Student
from app.models.user import User
from app.repositories.base import BaseStore


class MongoStore(BaseStore):
    def __init__(self, uri: str = "mongodb://localhost:27017/ledger_db") -> None:
        self.uri = uri
        self.client: MongoClient = MongoClient(uri, serverSelectionTimeoutMS=5000)
        # Extract default db name if in URI, else 'ledger_db'
        parsed_db = uri.rsplit("/", 1)[-1].split("?")[0]
        self.db_name = parsed_db if parsed_db else "ledger_db"
        self.db = self.client[self.db_name]

        # Collections matching store/mongo
        self.col_plans = self.db["ledger_plans"]
        self.col_features = self.db["ledger_features"]
        self.col_subscriptions = self.db["ledger_subscriptions"]
        self.col_usage_events = self.db["ledger_usage_events"]
        self.col_entitlement_cache = self.db["ledger_entitlement_cache"]
        self.col_invoices = self.db["ledger_invoices"]
        self.col_coupons = self.db["ledger_coupons"]
        self.col_coupon_applications = self.db["ledger_coupon_applications"]
        self.col_students = self.db["students"]
        self.col_users = self.db["users"]

    def ping(self) -> bool:
        try:
            self.client.admin.command("ping")
            return True
        except Exception as e:
            logger.warning(f"MongoDB ping failed: {e}")
            return False

    def migrate(self) -> None:
        """
        Runs migrations replicating store/mongo/migrations.go:
        Creates collections and ensures compound, unique, and partial indexes.
        """
        try:
            # 1. Plans
            self.col_plans.create_index([("slug", ASCENDING), ("app_id", ASCENDING)], unique=True)
            self.col_plans.create_index([("app_id", ASCENDING), ("status", ASCENDING)])
            self.col_plans.create_index([("app_id", ASCENDING), ("created_at", ASCENDING)])

            # 2. Features
            self.col_features.create_index([("key", ASCENDING), ("app_id", ASCENDING)], unique=True)
            self.col_features.create_index([("app_id", ASCENDING), ("status", ASCENDING)])

            # 3. Subscriptions
            self.col_subscriptions.create_index([("tenant_id", ASCENDING), ("app_id", ASCENDING), ("status", ASCENDING)])
            self.col_subscriptions.create_index([("tenant_id", ASCENDING), ("app_id", ASCENDING), ("created_at", DESCENDING)])
            self.col_subscriptions.create_index([("plan_id", ASCENDING)])

            # 4. Usage Events - Migration 9 partial unique index!
            self.col_usage_events.create_index([
                ("tenant_id", ASCENDING), ("app_id", ASCENDING),
                ("feature_key", ASCENDING), ("timestamp", DESCENDING)
            ])
            self.col_usage_events.create_index([("timestamp", DESCENDING)])
            self.col_usage_events.create_index(
                [("idempotency_key", ASCENDING)],
                unique=True,
                partialFilterExpression={"idempotency_key": {"$type": "string", "$gt": ""}}
            )

            # 5. Entitlement cache
            self.col_entitlement_cache.create_index([("tenant_id", ASCENDING), ("app_id", ASCENDING)])
            self.col_entitlement_cache.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)

            # 6. Invoices
            self.col_invoices.create_index([("tenant_id", ASCENDING), ("app_id", ASCENDING), ("created_at", DESCENDING)])
            self.col_invoices.create_index([("app_id", ASCENDING), ("status", ASCENDING)])
            self.col_invoices.create_index([
                ("tenant_id", ASCENDING), ("app_id", ASCENDING),
                ("period_start", ASCENDING), ("period_end", ASCENDING)
            ])
            self.col_invoices.create_index([("subscription_id", ASCENDING)])

            # 7. Coupons & Applications
            self.col_coupons.create_index([("code", ASCENDING), ("app_id", ASCENDING)], unique=True)
            self.col_coupon_applications.create_index(
                [("coupon_id", ASCENDING), ("subscription_id", ASCENDING)],
                unique=True
            )

            # 8. Students & Users (Preserved)
            self.col_users.create_index([("useremail", ASCENDING)], unique=True)
            self.col_students.create_index([("createdAt", DESCENDING)])
            logger.info("MongoDB migrations completed successfully.")
        except PyMongoError as e:
            logger.error(f"MongoDB migration error: {e}")
            raise ErrUnavailable(f"Database migration failed: {e}") from e

    # ── Plan methods ──
    def create_plan(self, p: Plan) -> None:
        try:
            doc = p.to_dict()
            doc["_id"] = p.id
            self.col_plans.insert_one(doc)
        except DuplicateKeyError as e:
            raise ErrAlreadyExists(f"Plan with slug {p.slug!r} already exists") from e
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        try:
            doc = self.col_plans.find_one({"_id": plan_id})
            return Plan.from_dict(doc) if doc else None
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def get_plan_by_slug(self, slug: str, app_id: str = "default") -> Optional[Plan]:
        try:
            doc = self.col_plans.find_one({"slug": slug, "app_id": app_id})
            return Plan.from_dict(doc) if doc else None
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def list_plans(self, app_id: str = "default", status: Optional[str] = None) -> List[Plan]:
        try:
            query = {"app_id": app_id}
            if status:
                query["status"] = status
            docs = self.col_plans.find(query).sort("created_at", ASCENDING)
            return [Plan.from_dict(d) for d in docs]
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def update_plan(self, p: Plan) -> None:
        try:
            p.touch()
            doc = p.to_dict()
            res = self.col_plans.replace_one({"_id": p.id}, doc)
            if res.matched_count == 0:
                raise ErrPlanNotFound(f"Plan {p.id} not found")
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def delete_plan(self, plan_id: str) -> None:
        try:
            res = self.col_plans.delete_one({"_id": plan_id})
            if res.deleted_count == 0:
                raise ErrPlanNotFound(f"Plan {plan_id} not found")
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def archive_plan(self, plan_id: str) -> None:
        try:
            res = self.col_plans.update_one(
                {"_id": plan_id},
                {"$set": {"status": PlanStatus.ARCHIVED.value, "updated_at": utc_now().isoformat()}}
            )
            if res.matched_count == 0:
                raise ErrPlanNotFound(f"Plan {plan_id} not found")
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    # ── Feature catalog methods ──
    def create_feature(self, f: CatalogFeature) -> None:
        try:
            doc = f.to_dict()
            doc["_id"] = f.id
            self.col_features.insert_one(doc)
        except DuplicateKeyError as e:
            raise ErrAlreadyExists(f"Feature with key {f.key!r} already exists") from e
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def get_feature(self, feature_id: str) -> Optional[CatalogFeature]:
        try:
            doc = self.col_features.find_one({"_id": feature_id})
            return CatalogFeature.from_dict(doc) if doc else None
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def get_feature_by_key(self, key: str, app_id: str = "default") -> Optional[CatalogFeature]:
        try:
            doc = self.col_features.find_one({"key": key, "$or": [{"app_id": app_id}, {"is_global": True}]})
            return CatalogFeature.from_dict(doc) if doc else None
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def list_features(self, app_id: str = "default") -> List[CatalogFeature]:
        try:
            docs = self.col_features.find({"$or": [{"app_id": app_id}, {"is_global": True}]}).sort("created_at", ASCENDING)
            return [CatalogFeature.from_dict(d) for d in docs]
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def list_global_features(self) -> List[CatalogFeature]:
        try:
            docs = self.col_features.find({"is_global": True}).sort("created_at", ASCENDING)
            return [CatalogFeature.from_dict(d) for d in docs]
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def update_feature(self, f: CatalogFeature) -> None:
        try:
            f.touch()
            doc = f.to_dict()
            res = self.col_features.replace_one({"_id": f.id}, doc)
            if res.matched_count == 0:
                raise ErrFeatureNotFound(f"Feature {f.id} not found")
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def delete_feature(self, feature_id: str) -> None:
        try:
            res = self.col_features.delete_one({"_id": feature_id})
            if res.deleted_count == 0:
                raise ErrFeatureNotFound(f"Feature {feature_id} not found")
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def archive_feature(self, feature_id: str) -> None:
        try:
            res = self.col_features.update_one(
                {"_id": feature_id},
                {"$set": {"status": "archived", "updated_at": utc_now().isoformat()}}
            )
            if res.matched_count == 0:
                raise ErrFeatureNotFound(f"Feature {feature_id} not found")
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    # ── Subscription methods ──
    def create_subscription(self, s: Subscription) -> None:
        try:
            doc = s.to_dict()
            doc["_id"] = s.id
            self.col_subscriptions.insert_one(doc)
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def get_subscription(self, sub_id: str) -> Optional[Subscription]:
        try:
            doc = self.col_subscriptions.find_one({"_id": sub_id})
            return Subscription.from_dict(doc) if doc else None
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def get_active_subscription(self, tenant_id: str, app_id: str = "default") -> Optional[Subscription]:
        try:
            doc = self.col_subscriptions.find_one({
                "tenant_id": tenant_id,
                "app_id": app_id,
                "status": {"$in": [SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIALING.value]}
            })
            return Subscription.from_dict(doc) if doc else None
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def list_subscriptions(self, tenant_id: Optional[str] = None, app_id: str = "default") -> List[Subscription]:
        try:
            q = {"app_id": app_id}
            if tenant_id:
                q["tenant_id"] = tenant_id
            docs = self.col_subscriptions.find(q).sort("created_at", DESCENDING)
            return [Subscription.from_dict(d) for d in docs]
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def update_subscription(self, s: Subscription) -> None:
        try:
            s.touch()
            doc = s.to_dict()
            res = self.col_subscriptions.replace_one({"_id": s.id}, doc)
            if res.matched_count == 0:
                raise ErrSubscriptionNotFound(f"Subscription {s.id} not found")
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def cancel_subscription(self, sub_id: str, immediately: bool, now: Optional[datetime] = None) -> datetime:
        s = self.get_subscription(sub_id)
        if not s:
            raise ErrSubscriptionNotFound(f"subscription {sub_id} not found")
        if s.status == SubscriptionStatus.CANCELED:
            raise ErrSubscriptionCanceled(f"subscription {sub_id} is already canceled")
        if s.status == SubscriptionStatus.EXPIRED:
            raise ErrSubscriptionExpired(f"subscription {sub_id} is expired")

        n = now or utc_now()
        if immediately:
            self.col_subscriptions.update_one(
                {"_id": sub_id},
                {"$set": {
                    "canceled_at": n.isoformat(),
                    "cancel_at": n.isoformat(),
                    "ended_at": n.isoformat(),
                    "status": SubscriptionStatus.CANCELED.value,
                    "updated_at": utc_now().isoformat()
                }}
            )
            return n
        else:
            self.col_subscriptions.update_one(
                {"_id": sub_id},
                {"$set": {
                    "cancel_at": s.current_period_end.isoformat(),
                    "updated_at": utc_now().isoformat()
                }}
            )
            return s.current_period_end

    def pause_subscription(self, sub_id: str, at: datetime) -> bool:
        res = self.col_subscriptions.update_one(
            {
                "_id": sub_id,
                "status": {"$in": [SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIALING.value]}
            },
            {"$set": {
                "status": SubscriptionStatus.PAUSED.value,
                "paused_at": at.isoformat(),
                "updated_at": utc_now().isoformat()
            }}
        )
        return res.modified_count > 0

    def resume_subscription(self, sub_id: str, r: Resume) -> bool:
        filter_q = {"_id": sub_id, "status": SubscriptionStatus.PAUSED.value}
        if r.paused_at is not None:
            filter_q["paused_at"] = r.paused_at.isoformat()

        update_q: Dict = {
            "status": r.status.value,
            "paused_at": None,
            "updated_at": utc_now().isoformat()
        }
        if r.period_end:
            update_q["current_period_end"] = r.period_end.isoformat()
        if r.trial_end:
            update_q["trial_end"] = r.trial_end.isoformat()
        if r.stretch:
            update_q["stretch"] = r.stretch.to_dict()

        res = self.col_subscriptions.update_one(filter_q, {"$set": update_q})
        return res.modified_count > 0

    def change_subscription_plan(self, sub_id: str, plan_id: str, quantity: Dict[str, int]) -> bool:
        res = self.col_subscriptions.update_one(
            {
                "_id": sub_id,
                "status": {"$nin": [SubscriptionStatus.CANCELED.value, SubscriptionStatus.EXPIRED.value]}
            },
            {"$set": {
                "plan_id": plan_id,
                "quantity": quantity or {},
                "updated_at": utc_now().isoformat()
            }}
        )
        return res.modified_count > 0

    def set_subscription_provider(self, sub_id: str, provider_id: str, provider_name: str) -> None:
        res = self.col_subscriptions.update_one(
            {"_id": sub_id},
            {"$set": {
                "provider_id": provider_id,
                "provider_name": provider_name,
                "updated_at": utc_now().isoformat()
            }}
        )
        if res.matched_count == 0:
            raise ErrSubscriptionNotFound(f"subscription {sub_id} not found")

    # ── Meter methods ──
    def ingest_batch(self, events: List[UsageEvent]) -> None:
        if not events:
            return
        docs = []
        for e in events:
            d = e.to_dict()
            d["_id"] = e.id
            docs.append(d)
        try:
            # Ordered=False to allow other items to insert if a duplicate key occurs
            self.col_usage_events.insert_many(docs, ordered=False)
        except DuplicateKeyError:
            pass  # Idempotent events safely ignored
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def aggregate(self, tenant_id: str, app_id: str, feature_key: str, period: Period, start: Optional[datetime] = None, end: Optional[datetime] = None) -> int:
        match_q: Dict = {
            "tenant_id": tenant_id,
            "app_id": app_id,
            "feature_key": feature_key
        }
        ts_q = {}
        if start:
            ts_q["$gte"] = start.isoformat()
        if end:
            ts_q["$lt"] = end.isoformat()
        if ts_q:
            match_q["timestamp"] = ts_q

        pipeline = [
            {"$match": match_q},
            {"$group": {"_id": None, "total": {"$sum": "$quantity"}}}
        ]
        try:
            res = list(self.col_usage_events.aggregate(pipeline))
            return int(res[0]["total"]) if res else 0
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def query_usage(self, tenant_id: str, app_id: str, feature_key: Optional[str] = None, start: Optional[datetime] = None, end: Optional[datetime] = None) -> List[UsageEvent]:
        q: Dict = {"tenant_id": tenant_id, "app_id": app_id}
        if feature_key:
            q["feature_key"] = feature_key
        ts_q = {}
        if start:
            ts_q["$gte"] = start.isoformat()
        if end:
            ts_q["$lt"] = end.isoformat()
        if ts_q:
            q["timestamp"] = ts_q

        try:
            docs = self.col_usage_events.find(q).sort("timestamp", DESCENDING)
            return [UsageEvent.from_dict(d) for d in docs]
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def purge_usage(self, before: datetime) -> int:
        try:
            res = self.col_usage_events.delete_many({"timestamp": {"$lt": before.isoformat()}})
            return res.deleted_count
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    # ── Entitlement cache methods ──
    def get_cached_entitlement(self, tenant_id: str, app_id: str, feature_key: str) -> Optional[EntitlementResult]:
        try:
            doc = self.col_entitlement_cache.find_one({
                "tenant_id": tenant_id,
                "app_id": app_id,
                "feature_key": feature_key,
                "expires_at": {"$gt": utc_now().isoformat()}
            })
            if doc and "result" in doc:
                return EntitlementResult.from_dict(doc["result"])
            return None
        except PyMongoError as e:
            return None  # Best-effort cache

    def set_cached_entitlement(self, tenant_id: str, app_id: str, feature_key: str, result: EntitlementResult, ttl_seconds: float) -> None:
        try:
            expires_at = utc_now() + timedelta(seconds=ttl_seconds)
            self.col_entitlement_cache.update_one(
                {"tenant_id": tenant_id, "app_id": app_id, "feature_key": feature_key},
                {"$set": {
                    "result": result.to_dict(),
                    "expires_at": expires_at.isoformat(),
                    "updated_at": utc_now().isoformat()
                }},
                upsert=True
            )
        except PyMongoError:
            pass  # Best-effort

    def invalidate_entitlements(self, tenant_id: str, app_id: str) -> None:
        try:
            self.col_entitlement_cache.delete_many({"tenant_id": tenant_id, "app_id": app_id})
        except PyMongoError:
            pass

    def invalidate_feature_entitlement(self, tenant_id: str, app_id: str, feature_key: str) -> None:
        try:
            self.col_entitlement_cache.delete_one({"tenant_id": tenant_id, "app_id": app_id, "feature_key": feature_key})
        except PyMongoError:
            pass

    # ── Invoice methods ──
    def create_invoice(self, inv: Invoice) -> None:
        try:
            doc = inv.to_dict()
            doc["_id"] = inv.id
            self.col_invoices.insert_one(doc)
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def get_invoice(self, inv_id: str) -> Optional[Invoice]:
        try:
            doc = self.col_invoices.find_one({"_id": inv_id})
            return Invoice.from_dict(doc) if doc else None
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def list_invoices(self, tenant_id: Optional[str] = None, app_id: str = "default") -> List[Invoice]:
        try:
            q = {"app_id": app_id}
            if tenant_id:
                q["tenant_id"] = tenant_id
            docs = self.col_invoices.find(q).sort("created_at", DESCENDING)
            return [Invoice.from_dict(d) for d in docs]
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def update_invoice(self, inv: Invoice) -> None:
        try:
            inv.touch()
            doc = inv.to_dict()
            res = self.col_invoices.replace_one({"_id": inv.id}, doc)
            if res.matched_count == 0:
                raise ErrInvoiceNotFound(f"Invoice {inv.id} not found")
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def get_invoice_by_period(self, tenant_id: str, app_id: str, period_start: datetime, period_end: datetime) -> Optional[Invoice]:
        try:
            doc = self.col_invoices.find_one({
                "tenant_id": tenant_id,
                "app_id": app_id,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "status": {"$ne": InvoiceStatus.VOIDED.value}
            })
            return Invoice.from_dict(doc) if doc else None
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def list_pending_invoices(self, app_id: str = "default") -> List[Invoice]:
        try:
            docs = self.col_invoices.find({"app_id": app_id, "status": InvoiceStatus.PENDING.value}).sort("created_at", ASCENDING)
            return [Invoice.from_dict(d) for d in docs]
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def mark_invoice_paid(self, inv_id: str, paid_at: datetime, payment_ref: str) -> None:
        res = self.col_invoices.update_one(
            {"_id": inv_id},
            {"$set": {
                "status": InvoiceStatus.PAID.value,
                "paid_at": paid_at.isoformat(),
                "payment_ref": payment_ref,
                "updated_at": utc_now().isoformat()
            }}
        )
        if res.matched_count == 0:
            raise ErrInvoiceNotFound(f"Invoice {inv_id} not found")

    def mark_invoice_voided(self, inv_id: str, reason: str) -> None:
        res = self.col_invoices.update_one(
            {"_id": inv_id},
            {"$set": {
                "status": InvoiceStatus.VOIDED.value,
                "voided_at": utc_now().isoformat(),
                "void_reason": reason,
                "updated_at": utc_now().isoformat()
            }}
        )
        if res.matched_count == 0:
            raise ErrInvoiceNotFound(f"Invoice {inv_id} not found")

    def set_invoice_provider(self, inv_id: str, provider_id: str, provider_name: str) -> None:
        res = self.col_invoices.update_one(
            {"_id": inv_id},
            {"$set": {
                "provider_id": provider_id,
                "provider_name": provider_name,
                "updated_at": utc_now().isoformat()
            }}
        )
        if res.matched_count == 0:
            raise ErrInvoiceNotFound(f"Invoice {inv_id} not found")

    # ── Coupon methods ──
    def create_coupon(self, c: Coupon) -> None:
        try:
            doc = c.to_dict()
            doc["_id"] = c.id
            self.col_coupons.insert_one(doc)
        except DuplicateKeyError as e:
            raise ErrAlreadyExists(f"Coupon {c.code} already exists") from e
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def get_coupon(self, code: str, app_id: str = "default") -> Optional[Coupon]:
        try:
            doc = self.col_coupons.find_one({"code": code.strip().upper(), "app_id": app_id})
            return Coupon.from_dict(doc) if doc else None
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def get_coupon_by_id(self, coupon_id: str) -> Optional[Coupon]:
        try:
            doc = self.col_coupons.find_one({"_id": coupon_id})
            return Coupon.from_dict(doc) if doc else None
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def list_coupons(self, app_id: str = "default") -> List[Coupon]:
        try:
            docs = self.col_coupons.find({"app_id": app_id}).sort("created_at", DESCENDING)
            return [Coupon.from_dict(d) for d in docs]
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def update_coupon(self, c: Coupon) -> None:
        try:
            c.touch()
            doc = c.to_dict()
            res = self.col_coupons.replace_one({"_id": c.id}, doc)
            if res.matched_count == 0:
                raise ErrCouponNotFound(f"Coupon {c.id} not found")
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def delete_coupon(self, coupon_id: str) -> None:
        try:
            res = self.col_coupons.delete_one({"_id": coupon_id})
            if res.deleted_count == 0:
                raise ErrCouponNotFound(f"Coupon {coupon_id} not found")
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def apply_coupon(self, sub_id: str, coupon_id: str) -> None:
        try:
            app = CouponApplication(coupon_id=coupon_id, subscription_id=sub_id)
            doc = app.to_dict()
            doc["_id"] = app.id
            self.col_coupon_applications.insert_one(doc)
        except DuplicateKeyError:
            pass  # Already applied

    def list_applied_coupons(self, sub_id: str) -> List[Coupon]:
        try:
            apps = list(self.col_coupon_applications.find({"subscription_id": sub_id}))
            coupon_ids = [a["coupon_id"] for a in apps]
            if not coupon_ids:
                return []
            docs = self.col_coupons.find({"_id": {"$in": coupon_ids}})
            return [Coupon.from_dict(d) for d in docs]
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def redeem_coupon(self, sub_id: str, coupon_id: str) -> None:
        c = self.get_coupon_by_id(coupon_id)
        if not c:
            raise ErrCouponNotFound(f"coupon {coupon_id} not found")
        if c.max_redemptions > 0 and c.times_redeemed >= c.max_redemptions:
            raise ErrCouponDepleted(f"coupon {c.code} max redemptions reached")

        self.apply_coupon(sub_id, coupon_id)
        self.col_coupons.update_one(
            {"_id": coupon_id},
            {"$inc": {"times_redeemed": 1}, "$set": {"updated_at": utc_now().isoformat()}}
        )

    # ── Lifecycle clock methods ──
    def list_due_subscriptions(self, due_before: datetime, statuses: List[str]) -> List[Subscription]:
        try:
            docs = self.col_subscriptions.find({
                "status": {"$in": statuses},
                "current_period_end": {"$lte": due_before.isoformat()}
            })
            return [Subscription.from_dict(d) for d in docs]
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def list_overdue_invoices(self, now: datetime) -> List[Invoice]:
        try:
            docs = self.col_invoices.find({
                "status": InvoiceStatus.PENDING.value,
                "due_date": {"$lt": now.isoformat()}
            })
            return [Invoice.from_dict(d) for d in docs]
        except PyMongoError as e:
            raise ErrUnavailable(str(e)) from e

    def end_subscription_trial(self, sub_id: str, now: datetime) -> bool:
        res = self.col_subscriptions.update_one(
            {
                "_id": sub_id,
                "status": SubscriptionStatus.TRIALING.value,
                "trial_end": {"$lte": now.isoformat()}
            },
            {"$set": {
                "status": SubscriptionStatus.ACTIVE.value,
                "updated_at": utc_now().isoformat()
            }}
        )
        return res.modified_count > 0

    def enact_subscription_cancel(self, sub_id: str, now: datetime) -> bool:
        res = self.col_subscriptions.update_one(
            {
                "_id": sub_id,
                "status": {"$nin": [SubscriptionStatus.CANCELED.value, SubscriptionStatus.EXPIRED.value]},
                "cancel_at": {"$lte": now.isoformat()}
            },
            {"$set": {
                "status": SubscriptionStatus.CANCELED.value,
                "canceled_at": now.isoformat(),
                "ended_at": now.isoformat(),
                "updated_at": utc_now().isoformat()
            }}
        )
        return res.modified_count > 0

    def advance_subscription_period(self, sub_id: str, from_end: datetime, next_start: datetime, next_end: datetime, now: datetime) -> bool:
        res = self.col_subscriptions.update_one(
            {
                "_id": sub_id,
                "status": {"$in": [SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIALING.value, SubscriptionStatus.PAST_DUE.value]},
                "current_period_end": from_end.isoformat(),
                "$or": [{"cancel_at": None}, {"cancel_at": {"$gt": from_end.isoformat()}}]
            },
            {"$set": {
                "current_period_start": next_start.isoformat(),
                "current_period_end": next_end.isoformat(),
                "updated_at": utc_now().isoformat()
            }}
        )
        return res.modified_count > 0

    def mark_invoice_past_due(self, inv_id: str, now: datetime) -> bool:
        res = self.col_invoices.update_one(
            {
                "_id": inv_id,
                "status": InvoiceStatus.PENDING.value,
                "due_date": {"$lt": now.isoformat()}
            },
            {"$set": {
                "status": InvoiceStatus.PAST_DUE.value,
                "updated_at": utc_now().isoformat()
            }}
        )
        return res.modified_count > 0

    # ── Existing Project: Students & Users ──
    def create_student(self, student: Student) -> Student:
        doc = student.to_dict()
        self.col_students.insert_one(doc)
        return student

    def get_all_students(self) -> List[Student]:
        docs = self.col_students.find().sort("createdAt", DESCENDING)
        return [Student.from_dict(d) for d in docs]

    def get_student_by_id(self, student_id: str) -> Optional[Student]:
        doc = self.col_students.find_one({"_id": student_id}) or self.col_students.find_one({"id": student_id})
        return Student.from_dict(doc) if doc else None

    def update_student(self, student_id: str, updates: Dict) -> Optional[Student]:
        set_fields = {}
        if "name" in updates:
            set_fields["name"] = str(updates["name"]).strip()
        if "age" in updates:
            set_fields["age"] = int(updates["age"])
        if "grade" in updates:
            set_fields["grade"] = str(updates["grade"]).strip().upper()
        if "city" in updates:
            set_fields["city"] = str(updates["city"]).strip()

        res = self.col_students.find_one_and_update(
            {"$or": [{"_id": student_id}, {"id": student_id}]},
            {"$set": set_fields},
            return_document=pymongo.ReturnDocument.AFTER
        )
        return Student.from_dict(res) if res else None

    def delete_student(self, student_id: str) -> bool:
        res = self.col_students.delete_one({"$or": [{"_id": student_id}, {"id": student_id}]})
        return res.deleted_count > 0

    def create_user(self, user: User) -> User:
        doc = user.to_dict()
        doc["_id"] = user.id
        self.col_users.insert_one(doc)
        return user

    def get_user_by_email(self, email: str) -> Optional[User]:
        doc = self.col_users.find_one({"useremail": email.strip().lower()})
        return User.from_dict(doc) if doc else None
