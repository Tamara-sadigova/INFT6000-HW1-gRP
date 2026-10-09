"""Benchmark harness: sync vs. async gRPC clients for the Textbook Rental Hub.

Compares three client execution models against a running server by
repeatedly calling ``SearchBooks``:

* ``sync-seq``  -- sequential blocking calls on one thread (baseline).
* ``sync-pool`` -- blocking calls dispatched through a ThreadPoolExecutor.
* ``async``     -- ``grpc.aio`` with ``asyncio.gather`` bounded by a
  ``asyncio.Semaphore``.

Usage examples::

    python benchmark.py
    python benchmark.py --requests 1000 --concurrency 1 10 50 100 \\
        --out benchmark_results.json
    python benchmark.py --modes sync-pool async --concurrency 10 50
    python benchmark.py --target localhost:50051 --warmup 50

Start a server first (for example ``python -m src.server.async_server``).
"""

import argparse
import asyncio
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from typing import List, Optional, Tuple

import grpc

from proto import rental_pb2 as pb2
from proto import rental_pb2_grpc as pb2_grpc

QUERIES: List[str] = [
    "clean",
    "design",
    "algorithms",
    "programming",
    "code",
    "software",
    "patterns",
    "introduction",
    "language",
    "structure",
]

MODES: List[str] = ["sync-seq", "sync-pool", "async"]

# (latency in ms, call succeeded)
Sample = Tuple[float, bool]


@dataclass
class RunResult:
    """Metrics for a single mode/concurrency run."""

    mode: str
    concurrency: int
    total_requests: int
    wall_time_s: float
    throughput_rps: float
    latency_mean_ms: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_min_ms: float
    latency_max_ms: float
    errors: int


def percentile(sorted_values: List[float], pct: float) -> float:
    """Return the pct-th percentile using linear interpolation.

    ``sorted_values`` must be sorted ascending; ``pct`` is in [0, 100].
    """
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (pct / 100.0) * (len(sorted_values) - 1)
    low = int(rank)
    high = min(low + 1, len(sorted_values) - 1)
    frac = rank - low
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * frac


def build_result(
    mode: str,
    concurrency: int,
    total: int,
    wall_s: float,
    samples: List[Sample],
) -> RunResult:
    """Aggregate raw samples into a RunResult."""
    latencies = sorted(lat for lat, ok in samples if ok)
    errors = sum(1 for _, ok in samples if not ok)
    return RunResult(
        mode=mode,
        concurrency=concurrency,
        total_requests=total,
        wall_time_s=wall_s,
        throughput_rps=total / wall_s if wall_s > 0 else 0.0,
        latency_mean_ms=statistics.fmean(latencies) if latencies else 0.0,
        latency_p50_ms=percentile(latencies, 50),
        latency_p95_ms=percentile(latencies, 95),
        latency_p99_ms=percentile(latencies, 99),
        latency_min_ms=latencies[0] if latencies else 0.0,
        latency_max_ms=latencies[-1] if latencies else 0.0,
        errors=errors,
    )


def query_for(i: int) -> str:
    """Deterministically pick the query for request ``i``."""
    return QUERIES[i % len(QUERIES)]


# --------------------------------------------------------------------------
# Blocking clients
# --------------------------------------------------------------------------
def sync_call(stub: pb2_grpc.TextbookRentalServiceStub, i: int) -> Sample:
    """Issue one blocking SearchBooks call and time it."""
    start = time.perf_counter()
    try:
        stub.SearchBooks(pb2.SearchRequest(query=query_for(i)))
        ok = True
    except Exception:  # noqa: BLE001 - any failure counts as an error
        ok = False
    return (time.perf_counter() - start) * 1000.0, ok


def run_sync_seq(target: str, requests: int, warmup: int) -> RunResult:
    """Sequential blocking baseline."""
    channel = grpc.insecure_channel(target)
    try:
        stub = pb2_grpc.TextbookRentalServiceStub(channel)
        for i in range(warmup):
            sync_call(stub, i)
        samples: List[Sample] = []
        start = time.perf_counter()
        for i in range(requests):
            samples.append(sync_call(stub, i))
        wall = time.perf_counter() - start
    finally:
        channel.close()
    return build_result("sync-seq", 1, requests, wall, samples)


def run_sync_pool(
    target: str, requests: int, warmup: int, concurrency: int
) -> RunResult:
    """Blocking calls dispatched through a thread pool."""
    channel = grpc.insecure_channel(target)
    executor = ThreadPoolExecutor(max_workers=concurrency)
    try:
        stub = pb2_grpc.TextbookRentalServiceStub(channel)
        warm = [executor.submit(sync_call, stub, i) for i in range(warmup)]
        for future in warm:
            future.result()
        start = time.perf_counter()
        futures = [executor.submit(sync_call, stub, i) for i in range(requests)]
        samples = [future.result() for future in futures]
        wall = time.perf_counter() - start
    finally:
        executor.shutdown(wait=True)
        channel.close()
    return build_result("sync-pool", concurrency, requests, wall, samples)


# --------------------------------------------------------------------------
# Async client
# --------------------------------------------------------------------------
async def async_call(
    stub: pb2_grpc.TextbookRentalServiceStub,
    i: int,
    semaphore: Optional[asyncio.Semaphore],
) -> Sample:
    """Issue one grpc.aio SearchBooks call and time it.

    Latency is measured after the semaphore is acquired, so it reflects
    the RPC itself rather than time spent queued client-side.
    """
    if semaphore is None:
        return await _timed_async_call(stub, i)
    async with semaphore:
        return await _timed_async_call(stub, i)


async def _timed_async_call(
    stub: pb2_grpc.TextbookRentalServiceStub, i: int
) -> Sample:
    start = time.perf_counter()
    try:
        await stub.SearchBooks(pb2.SearchRequest(query=query_for(i)))
        ok = True
    except Exception:  # noqa: BLE001 - any failure counts as an error
        ok = False
    return (time.perf_counter() - start) * 1000.0, ok


async def _run_async(
    target: str, requests: int, warmup: int, concurrency: int
) -> RunResult:
    channel = grpc.aio.insecure_channel(target)
    try:
        stub = pb2_grpc.TextbookRentalServiceStub(channel)
        semaphore = asyncio.Semaphore(concurrency)
        await asyncio.gather(
            *(async_call(stub, i, semaphore) for i in range(warmup))
        )
        start = time.perf_counter()
        samples = await asyncio.gather(
            *(async_call(stub, i, semaphore) for i in range(requests))
        )
        wall = time.perf_counter() - start
    finally:
        await channel.close()
    return build_result("async", concurrency, requests, wall, list(samples))


def run_async(
    target: str, requests: int, warmup: int, concurrency: int
) -> RunResult:
    """Run the grpc.aio benchmark to completion."""
    return asyncio.run(_run_async(target, requests, warmup, concurrency))


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def print_header() -> None:
    """Print the column header for per-run summary lines."""
    print(
        f"{'mode':<10} {'conc':>5} {'reqs':>6} {'wall(s)':>9} "
        f"{'req/s':>10} {'mean':>8} {'p50':>8} {'p95':>8} {'p99':>8} "
        f"{'min':>8} {'max':>8} {'err':>5}"
    )


def print_result(r: RunResult) -> None:
    """Print one aligned summary line."""
    print(
        f"{r.mode:<10} {r.concurrency:>5} {r.total_requests:>6} "
        f"{r.wall_time_s:>9.3f} {r.throughput_rps:>10.1f} "
        f"{r.latency_mean_ms:>8.2f} {r.latency_p50_ms:>8.2f} "
        f"{r.latency_p95_ms:>8.2f} {r.latency_p99_ms:>8.2f} "
        f"{r.latency_min_ms:>8.2f} {r.latency_max_ms:>8.2f} "
        f"{r.errors:>5}",
        flush=True,
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Benchmark sync vs. async gRPC clients (SearchBooks)."
    )
    parser.add_argument("--target", default="localhost:50052")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument(
        "--concurrency", type=int, nargs="+", default=[10, 50, 100]
    )
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument(
        "--modes", nargs="+", choices=MODES, default=list(MODES)
    )
    parser.add_argument("--out", default="benchmark_results.json")
    return parser.parse_args()


def main() -> None:
    """Run the requested sweep and write results to JSON."""
    args = parse_args()
    results: List[RunResult] = []
    print_header()

    for mode in args.modes:
        if mode == "sync-seq":
            result = run_sync_seq(args.target, args.requests, args.warmup)
            results.append(result)
            print_result(result)
            continue
        for conc in args.concurrency:
            if mode == "sync-pool":
                result = run_sync_pool(
                    args.target, args.requests, args.warmup, conc
                )
            else:
                result = run_async(
                    args.target, args.requests, args.warmup, conc
                )
            results.append(result)
            print_result(result)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump([asdict(r) for r in results], fh, indent=2)
    print(f"\nWrote {len(results)} runs to {args.out}")


if __name__ == "__main__":
    main()
