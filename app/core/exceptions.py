"""
Sentinel exceptions and error classifications reproducing errors.go.
"""
from __future__ import annotations


class LedgerError(Exception):
    """Base error for all Ledger billing exceptions."""
    pass


class ErrNotFound(LedgerError):
    pass


class ErrPlanNotFound(ErrNotFound):
    pass


class ErrPlanArchived(LedgerError):
    pass


class ErrPlanInactive(LedgerError):
    pass


class ErrFeatureNotFound(ErrNotFound):
    pass


class ErrFeatureArchived(LedgerError):
    pass


class ErrSubscriptionNotFound(ErrNotFound):
    pass


class ErrNoActiveSubscription(ErrNotFound):
    pass


class ErrSubscriptionCanceled(LedgerError):
    pass


class ErrSubscriptionExpired(LedgerError):
    pass


class ErrSubscriptionPaused(LedgerError):
    pass


class ErrQuotaExceeded(LedgerError):
    pass


class ErrInvalidInput(LedgerError, ValueError):
    pass


class ErrAlreadyExists(LedgerError):
    pass


class ErrUnavailable(LedgerError):
    """Raised when the underlying store or network dependency is unavailable."""
    pass


class ErrCouponNotFound(ErrNotFound):
    pass


class ErrCouponExpired(LedgerError):
    pass


class ErrCouponDepleted(LedgerError):
    pass


class ErrCouponInvalid(LedgerError):
    pass


class ErrInvoiceNotFound(ErrNotFound):
    pass


class ErrInvoiceNotPending(LedgerError):
    pass


class ErrInvoiceAlreadyPaid(LedgerError):
    pass


class ErrInvoiceVoided(LedgerError):
    pass


class ErrInvalidPricing(LedgerError):
    pass


class ErrInvalidTiers(LedgerError):
    pass


def is_not_found(err: BaseException) -> bool:
    return isinstance(err, ErrNotFound)


def is_quota_error(err: BaseException) -> bool:
    return isinstance(err, ErrQuotaExceeded)


def is_retryable(err: BaseException) -> bool:
    return isinstance(err, ErrUnavailable)
