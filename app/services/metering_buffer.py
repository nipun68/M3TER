"""
High-throughput asynchronous usage metering buffer reproducing meterFlushWorker in ledger.go.
Supports in-memory batching, periodic flushing, retained retry queue with exponential backoff,
and graceful shutdown.
"""
from __future__ import annotations
import asyncio
import time
from typing import List, Optional
from app.config.logging import logger
from app.core.exceptions import ErrUnavailable
from app.models.meter import UsageEvent
from app.plugins.registry import PluginRegistry
from app.repositories.base import BaseStore


class MeteringBuffer:
    def __init__(
        self,
        store: BaseStore,
        plugins: PluginRegistry,
        batch_size: int = 100,
        flush_interval_seconds: float = 5.0,
        retry_initial_seconds: float = 1.0,
        retry_max_seconds: float = 30.0,
        max_buffer_capacity: int = 100000,
    ) -> None:
        self.store = store
        self.plugins = plugins
        self.batch_size = max(1, batch_size)
        self.flush_interval = flush_interval_seconds
        self.retry_initial = retry_initial_seconds
        self.retry_max = retry_max_seconds
        self.max_capacity = max_buffer_capacity

        self._queue: asyncio.Queue[UsageEvent] = asyncio.Queue(maxsize=max_buffer_capacity)
        self._held_retry_events: List[UsageEvent] = []
        self._retry_delay = retry_initial_seconds
        self._next_retry_time: float = 0.0
        self._worker_task: Optional[asyncio.Task] = None
        self._stopping = False

    async def start(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._stopping = False
            self._worker_task = asyncio.create_task(self._flush_loop())
            logger.info("Metering buffer flush worker started.")

    async def stop(self) -> None:
        self._stopping = True
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        # Drain remaining events in queue
        await self.flush(final=True)
        logger.info("Metering buffer flush worker stopped.")

    async def enqueue(self, event: UsageEvent) -> None:
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            # Drop unkeyed, raise if capacity exceeded
            if event.idempotency_key:
                # Retain keyed event directly
                self._held_retry_events.append(event)
            else:
                logger.warning("Meter buffer queue full; dropped unkeyed event")

    def enqueue_sync(self, event: UsageEvent) -> None:
        """Synchronous ingestion fallback (e.g. from sync endpoints, CLI, or unit tests)."""
        try:
            self.store.ingest_batch([event])
        except Exception as e:
            if event.idempotency_key:
                self._held_retry_events.append(event)
            logger.warning(f"Direct sync ingest failed: {e}")

    def flush_sync(self) -> None:
        """Synchronously drain and ingest any queued events."""
        batch: List[UsageEvent] = []
        while not self._queue.empty():
            try:
                batch.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if batch:
            try:
                self.store.ingest_batch(batch)
            except Exception as e:
                logger.error(f"Sync flush failed: {e}")

    async def _flush_loop(self) -> None:
        while not self._stopping:
            try:
                await asyncio.sleep(self.flush_interval)
                await self.flush(final=False)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in meter flush loop: {e}")

    async def flush(self, final: bool = False) -> None:
        # Collect batch from queue
        batch: List[UsageEvent] = []
        while not self._queue.empty() and len(batch) < self.batch_size:
            try:
                batch.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break

        now = time.time()
        retry_due = bool(self._held_retry_events and (final or now >= self._next_retry_time))

        send: List[UsageEvent] = []
        if retry_due:
            send.extend(self._held_retry_events)
            send.extend(batch)
        else:
            send.extend(batch)

        if not send:
            return

        start_time = time.time()
        sent = 0
        err: Optional[Exception] = None

        while sent < len(send):
            chunk = send[sent : sent + self.batch_size]
            try:
                self.store.ingest_batch(chunk)
                sent += len(chunk)
            except Exception as e:
                err = e
                break

        elapsed_ms = (time.time() - start_time) * 1000.0

        if sent > 0:
            self.plugins.emit_usage_flushed(sent, elapsed_ms)

        if err is None:
            if retry_due:
                self._held_retry_events.clear()
                self._retry_delay = self.retry_initial
            return

        # Failure handling: retain keyed events for retry
        unsent = send[sent:]
        keyed = [e for e in unsent if e.idempotency_key]
        lost = len(unsent) - len(keyed)

        if final:
            # Can't retry anymore
            self._held_retry_events.clear()
            logger.error(f"Final flush failed, lost {len(unsent)} events: {err}")
        else:
            self._held_retry_events = keyed
            self._retry_delay = min(self._retry_delay * 2, self.retry_max)
            self._next_retry_time = time.time() + self._retry_delay
            logger.error(
                f"Failed to flush meter batch: {err}. Retained {len(keyed)} keyed events for retry in {self._retry_delay}s. Lost {lost} unkeyed events."
            )
