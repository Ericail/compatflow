"""Offline cross-client analysis of one immutable live capture."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from compatflow.adapters import ADAPTER_NAMES, AdapterName
from compatflow.capture.models import CaptureRecord
from compatflow.matrix import CompatibilityMatrix, run_matrix
from compatflow.replay.ephemeral import replay_server
from compatflow.wire_oracle import WireReport, evaluate_wire


class CaptureEvaluation(BaseModel):
    """Wire baseline and client semantic matrix derived from one response hash."""

    model_config = ConfigDict(extra="forbid")

    capture_id: str
    response_sha256: str
    wire_report: WireReport
    wire_expectation_met: bool
    matrix: CompatibilityMatrix


async def evaluate_capture(
    capture: CaptureRecord,
    adapter_names: tuple[AdapterName, ...] = ADAPTER_NAMES,
) -> CaptureEvaluation:
    """Replay exact captured bytes through selected real SDK clients."""

    trace = capture.to_trace()
    wire_report = evaluate_wire(trace.events)
    expected_wire = capture.manifest.wire_expectation
    issue_codes = [issue.code for issue in wire_report.issues]
    if expected_wire.outcome == "compliant":
        wire_expectation_met = wire_report.passed
    else:
        wire_expectation_met = not wire_report.passed and set(
            expected_wire.issue_codes
        ).issubset(issue_codes)
    with replay_server(trace) as (server_url, _):
        matrix = await run_matrix(server_url, adapter_names)
    return CaptureEvaluation(
        capture_id=capture.capture_id,
        response_sha256=capture.response_sha256,
        wire_report=wire_report,
        wire_expectation_met=wire_expectation_met,
        matrix=matrix,
    )
