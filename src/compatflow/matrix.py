"""Cross-client compatibility matrix execution and reporting."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ConfigDict, Field

from compatflow.adapters import AdapterName, get_adapter
from compatflow.oracle import evaluate
from compatflow.replay.models import GroundTruth


class MatrixCell(BaseModel):
    """Compact verdict for one client adapter and one trace."""

    model_config = ConfigDict(extra="forbid")

    adapter: str
    adapter_version: str
    trace_id: str
    transformation: str
    chunks_seen: int = Field(ge=0)
    semantic_passed: bool
    expected_outcome: str
    expected_issue_codes: list[str]
    expectation_met: bool
    issue_codes: list[str]


class CompatibilityMatrix(BaseModel):
    """Deterministic summary of a complete adapter-by-trace experiment."""

    model_config = ConfigDict(extra="forbid")

    adapter_count: int = Field(ge=1)
    trace_count: int = Field(ge=1)
    total: int = Field(ge=1)
    semantic_passed: int = Field(ge=0)
    semantic_failed: int = Field(ge=0)
    expectations_met: int = Field(ge=0)
    unexpected: int = Field(ge=0)
    cells: list[MatrixCell]


@dataclass(frozen=True)
class _TraceCase:
    trace_id: str
    transformation: str
    ground_truth: GroundTruth
    expected_outcome: str
    expected_issue_codes: tuple[str, ...]
    adapter_overrides: dict[str, tuple[str, tuple[str, ...]]]


async def _fetch_cases(server_url: str) -> list[_TraceCase]:
    async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
        response = await client.get(f"{server_url.rstrip('/')}/_compatflow/traces")
        response.raise_for_status()
    cases = []
    for trace in response.json().get("traces", []):
        provenance = trace.get("provenance")
        transformation = (
            provenance.get("transformation") if isinstance(provenance, dict) else "canonical"
        )
        cases.append(
            _TraceCase(
                trace_id=trace["trace_id"],
                transformation=transformation,
                ground_truth=GroundTruth.model_validate(trace["ground_truth"]),
                expected_outcome=trace.get("expectation", {}).get("outcome", "compatible"),
                expected_issue_codes=tuple(
                    trace.get("expectation", {}).get("issue_codes", [])
                ),
                adapter_overrides={
                    name: (
                        override.get("outcome", "compatible"),
                        tuple(override.get("issue_codes", [])),
                    )
                    for name, override in trace.get("expectation", {})
                    .get("adapter_overrides", {})
                    .items()
                },
            )
        )
    if not cases:
        raise ValueError("replay server returned an empty trace catalog")
    return cases


async def run_matrix(
    server_url: str,
    adapter_names: tuple[AdapterName, ...],
) -> CompatibilityMatrix:
    """Run every selected adapter against every trace exposed by a replay server."""

    if not adapter_names:
        raise ValueError("select at least one adapter")
    cases = await _fetch_cases(server_url)
    cells = []
    for adapter_name in adapter_names:
        adapter = get_adapter(adapter_name)
        for case in cases:
            observed = await adapter.observe_url(server_url, case.trace_id)
            report = evaluate(observed, case.ground_truth)
            actual_issue_codes = [issue.code for issue in report.issues]
            expected_outcome, expected_issue_codes = case.adapter_overrides.get(
                adapter_name,
                (case.expected_outcome, case.expected_issue_codes),
            )
            if expected_outcome == "compatible":
                expectation_met = report.passed
            else:
                expectation_met = not report.passed and set(expected_issue_codes).issubset(
                    actual_issue_codes
                )
            cells.append(
                MatrixCell(
                    adapter=observed.adapter,
                    adapter_version=observed.adapter_version,
                    trace_id=case.trace_id,
                    transformation=case.transformation,
                    chunks_seen=observed.chunks_seen,
                    semantic_passed=report.passed,
                    expected_outcome=expected_outcome,
                    expected_issue_codes=list(expected_issue_codes),
                    expectation_met=expectation_met,
                    issue_codes=actual_issue_codes,
                )
            )
    semantic_passed = sum(cell.semantic_passed for cell in cells)
    expectations_met = sum(cell.expectation_met for cell in cells)
    return CompatibilityMatrix(
        adapter_count=len(adapter_names),
        trace_count=len(cases),
        total=len(cells),
        semantic_passed=semantic_passed,
        semantic_failed=len(cells) - semantic_passed,
        expectations_met=expectations_met,
        unexpected=len(cells) - expectations_met,
        cells=cells,
    )
