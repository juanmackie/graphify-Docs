"""Micro-batching evaluation for the remote extraction workload.

This intentionally does not change production behavior. Batch extraction needs
strict per-chunk attribution from the model; otherwise one malformed response
can lose several chunks. Run this after collecting real metrics from graph.json:

    python -m benchmarks.microbatch_eval --chunks 120 --latency 4 --concurrency 4
"""
from __future__ import annotations

import argparse
import math


def estimate(chunks: int, latency: float, concurrency: int, batch_size: int) -> dict[str, float]:
    requests = math.ceil(chunks / batch_size)
    # Conservative estimate: larger responses take proportionally more time,
    # with a small fixed prompt/network saving per combined request.
    batch_latency = latency * (0.35 + 0.65 * batch_size)
    wall_seconds = math.ceil(requests / concurrency) * batch_latency
    return {
        "requests": requests,
        "estimated_seconds": round(wall_seconds, 2),
        "speedup_vs_single": round((chunks / concurrency * latency) / wall_seconds, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", type=int, required=True)
    parser.add_argument("--latency", type=float, required=True)
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    for batch_size in (1, 2, 4):
        print(f"batch_size={batch_size}: {estimate(args.chunks, args.latency, args.concurrency, batch_size)}")


if __name__ == "__main__":
    main()
