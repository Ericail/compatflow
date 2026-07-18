"""CLI for deterministic offline evaluation of one capture artifact."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from compatflow.adapters import ADAPTER_NAMES, AdapterName
from compatflow.capture.evaluate import evaluate_capture
from compatflow.capture.models import CaptureRecord


async def _run(path: Path, adapters: tuple[AdapterName, ...]) -> int:
    capture = CaptureRecord.model_validate_json(path.read_text(encoding="utf-8"))
    try:
        result = await evaluate_capture(capture, adapters)
    except ValueError as error:
        print(json.dumps({"capture_id": capture.capture_id, "error": str(error)}, indent=2))
        return 1
    print(result.model_dump_json(indent=2))
    return 0 if result.wire_expectation_met and result.matrix.unexpected == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay one exact capture through client SDKs and both oracles",
    )
    parser.add_argument("capture", type=Path, help="capture JSON from compatflow-record")
    parser.add_argument(
        "--adapter",
        action="append",
        choices=ADAPTER_NAMES,
        help="adapter to run; repeat as needed (default: all)",
    )
    args = parser.parse_args()
    adapters = tuple(args.adapter) if args.adapter else ADAPTER_NAMES
    raise SystemExit(asyncio.run(_run(args.capture, adapters)))


if __name__ == "__main__":
    main()
