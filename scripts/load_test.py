"""Async load generator. Run ONLY against a server you own/are authorized to test.

Usage: python scripts/load_test.py --url http://127.0.0.1:8000 --requests 50 --concurrency 5
"""

import argparse
import asyncio
import json
import math
import statistics
import time

import httpx


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(values) - 1, math.ceil(len(values) * fraction) - 1)]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--api-key", default="")
    args = parser.parse_args()
    if not 1 <= args.requests <= 1000 or not 1 <= args.concurrency <= 50:
        parser.error("requests must be 1..1000 and concurrency 1..50")
    semaphore = asyncio.Semaphore(args.concurrency)
    elapsed: list[float] = []
    successes = 0
    headers = {"X-API-Key": args.api_key} if args.api_key else {}

    async with httpx.AsyncClient(timeout=30) as client:
        async def send(i: int) -> None:
            nonlocal successes
            async with semaphore:
                started = time.perf_counter()
                try:
                    response = await client.post(
                        args.url.rstrip("/") + "/v1/chat",
                        json={"user_id": f"load{i}", "thread_id": "t1", "message": "你好"},
                        headers=headers,
                    )
                    successes += int(response.status_code == 200)
                except httpx.RequestError:
                    pass
                finally:
                    elapsed.append((time.perf_counter() - started) * 1000)

        started = time.perf_counter()
        await asyncio.gather(*(send(i) for i in range(args.requests)))
        seconds = time.perf_counter() - started
    print(json.dumps({
        "requests": args.requests,
        "concurrency": args.concurrency,
        "successes": successes,
        "success_rate": round(successes / args.requests, 4),
        "throughput_rps": round(args.requests / seconds, 2),
        "mean_ms": round(statistics.mean(elapsed), 2),
        "p95_ms": round(percentile(elapsed, 0.95), 2),
        "p99_ms": round(percentile(elapsed, 0.99), 2),
        "note": "Local client-observed request latency; not TTFT or model-cost measurement",
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
