"""Command-line interface for failure-preserving trace reduction."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from compatflow.adapters import ADAPTER_NAMES, AdapterName
from compatflow.reducer import reduce_trace
from compatflow.replay.models import Trace


async def _run(source: Path, output: Path, adapter: AdapterName, *, force: bool) -> int:
    if output.exists() and not force:
        raise FileExistsError(f"output exists; pass --force to replace it: {output}")
    trace = Trace.model_validate_json(source.read_text(encoding="utf-8"))
    result = await reduce_trace(trace, adapter)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result.trace.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(result.model_dump_json(indent=2, exclude={"trace"}))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Minimize an SSE trace while preserving its exact oracle failure signature",
    )
    parser.add_argument("source", type=Path, help="input trace JSON")
    parser.add_argument("output", type=Path, help="output path for the reduced trace")
    parser.add_argument("--adapter", choices=ADAPTER_NAMES, default="openai-python")
    parser.add_argument("--force", action="store_true", help="replace an existing output file")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args.source, args.output, args.adapter, force=args.force)))


if __name__ == "__main__":
    main()
