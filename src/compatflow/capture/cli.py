"""CLI for recording a live stream and optionally importing it as a Trace."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from pydantic import BaseModel

from compatflow.capture.models import ExperimentManifest
from compatflow.capture.recorder import record_experiment
from compatflow.wire_oracle import evaluate_wire


def _write_json(path: Path, value: BaseModel, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"output exists; pass --force to replace it: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = value.model_dump(mode="json")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _check_output(path: Path | None, *, force: bool) -> None:
    if path is not None and path.exists() and not force:
        raise FileExistsError(f"output exists; pass --force to replace it: {path}")


async def _run(
    manifest_path: Path,
    output: Path,
    trace_output: Path | None,
    api_key_env: str,
    *,
    force: bool,
) -> int:
    _check_output(output, force=force)
    _check_output(trace_output, force=force)
    manifest = ExperimentManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    api_key = os.getenv(api_key_env)
    capture = await record_experiment(manifest, api_key=api_key)
    _write_json(output, capture, force=force)

    trace_error: str | None = None
    wire_report = None
    wire_expectation_met = False
    try:
        trace = capture.to_trace()
        wire_report = evaluate_wire(trace.events)
        expected_wire = manifest.wire_expectation
        actual_codes = [issue.code for issue in wire_report.issues]
        if expected_wire.outcome == "compliant":
            wire_expectation_met = wire_report.passed
        else:
            wire_expectation_met = not wire_report.passed and set(
                expected_wire.issue_codes
            ).issubset(actual_codes)
    except ValueError as error:
        trace = None
        trace_error = str(error)
    if trace_output is not None:
        if trace is not None:
            _write_json(trace_output, trace, force=force)
    summary = {
        "capture_id": capture.capture_id,
        "complete": capture.complete,
        "status_code": capture.status_code,
        "response_bytes": len(capture.response_bytes()),
        "response_sha256": capture.response_sha256,
        "capture_output": str(output),
        "trace_output": str(trace_output) if trace_output and trace_error is None else None,
        "trace_error": trace_error,
        "wire_report": wire_report.model_dump() if wire_report else None,
        "wire_expectation_met": wire_expectation_met,
        "failure": capture.failure.model_dump() if capture.failure else None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    succeeded = (
        capture.complete
        and capture.status_code is not None
        and 200 <= capture.status_code < 300
        and trace_error is None
        and wire_expectation_met
    )
    return 0 if succeeded else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record exact SSE bytes from one versioned server experiment",
    )
    parser.add_argument("manifest", type=Path, help="validated experiment manifest JSON")
    parser.add_argument("output", type=Path, help="raw capture artifact JSON")
    parser.add_argument("--trace-output", type=Path, help="optional imported Trace JSON")
    parser.add_argument(
        "--api-key-env",
        default="OPENAI_API_KEY",
        help="environment variable read at runtime; the key is never persisted",
    )
    parser.add_argument("--force", action="store_true", help="replace existing outputs")
    args = parser.parse_args()
    raise SystemExit(
        asyncio.run(
            _run(
                args.manifest,
                args.output,
                args.trace_output,
                args.api_key_env,
                force=args.force,
            )
        )
    )


if __name__ == "__main__":
    main()
