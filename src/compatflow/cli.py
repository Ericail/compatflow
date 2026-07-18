"""Command-line harness for running one adapter against one replay trace."""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

import httpx

from compatflow.adapters import OpenAIPythonAdapter
from compatflow.oracle import evaluate
from compatflow.replay.models import GroundTruth


async def _fetch_ground_truth(server_url: str, trace_id: str) -> GroundTruth:
    async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
        response = await client.get(f"{server_url.rstrip('/')}/_compatflow/traces")
        response.raise_for_status()
    catalog: dict[str, Any] = response.json()
    for trace in catalog.get("traces", []):
        if trace.get("trace_id") == trace_id:
            return GroundTruth.model_validate(trace["ground_truth"])
    raise ValueError(f"unknown trace: {trace_id}")


async def _run(server_url: str, trace_id: str) -> int:
    expected = await _fetch_ground_truth(server_url, trace_id)
    observed = await OpenAIPythonAdapter().observe_url(server_url, trace_id)
    report = evaluate(observed, expected)
    print(report.model_dump_json(indent=2))
    return 0 if report.passed else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run an OpenAI Python SDK compatibility check against CompatFlow replay",
    )
    parser.add_argument("trace_id", help="trace identifier from /_compatflow/traces")
    parser.add_argument("--server", default="http://127.0.0.1:8000", help="replay server URL")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args.server, args.trace_id)))


if __name__ == "__main__":
    main()
