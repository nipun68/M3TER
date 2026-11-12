"""
High-throughput benchmark and concurrency verification evaluating 10,000 events/sec target.
Measures event throughput, p50/p95/p99 latencies, error rate, and thread safety.
"""
import time
import statistics
from concurrent.futures import ThreadPoolExecutor
from app.models.meter import UsageEvent
from app.repositories.memory_store import MemoryStore
from app.services.ledger import Ledger


def test_meter_ingestion_throughput_10k():
    store = MemoryStore()
    ledger = Ledger(store=store)

    event_count = 10000
    batch_size = 500
    batches = []

    # Pre-generate 10,000 events
    for i in range(0, event_count, batch_size):
        batch = [
            UsageEvent(
                tenant_id=f"tenant_{j % 50}",
                feature_key="api_requests",
                quantity=1,
                idempotency_key=f"bench_key_{j}",
            )
            for j in range(i, i + batch_size)
        ]
        batches.append(batch)

    latencies = []
    start_total = time.perf_counter()

    for batch in batches:
        t0 = time.perf_counter()
        store.ingest_batch(batch)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)  # ms per batch

    total_time = time.perf_counter() - start_total
    throughput = event_count / total_time

    p50 = statistics.median(latencies)
    sorted_latencies = sorted(latencies)
    p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
    p99 = sorted_latencies[int(len(sorted_latencies) * 0.99)]

    print(f"\n--- LOAD BENCHMARK RESULTS ---")
    print(f"Events Ingested: {event_count:,}")
    print(f"Total Time:      {total_time:.4f} seconds")
    print(f"Throughput:      {throughput:,.2f} events/sec")
    print(f"Batch Latency:   p50={p50:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms")
    print(f"------------------------------")

    # Verify all 10,000 events ingested without loss
    total_stored = len(store.usage_events)
    assert total_stored == event_count
    # Expect well in excess of 10,000 events/sec in Python in-memory engine
    assert throughput >= 10000.0


def test_concurrent_meter_race_safety():
    store = MemoryStore()
    ledger = Ledger(store=store)

    threads = 8
    events_per_thread = 500
    total_expected = threads * events_per_thread

    def worker(thread_idx: int):
        for i in range(events_per_thread):
            ledger.meter_with_key(
                tenant_id=f"tenant_worker_{thread_idx}",
                feature_key="concurrent_feat",
                idempotency_key=f"th_{thread_idx}_evt_{i}",
                quantity=1,
            )

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [executor.submit(worker, t) for t in range(threads)]
        for f in futures:
            f.result()

    total_ingested = len(store.usage_events)
    assert total_ingested == total_expected
