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
    passed: bool
    issue_codes: list[str]


class CompatibilityMatrix(BaseModel):
    """Deterministic summary of a complete adapter-by-trace experiment."""

    model_config = ConfigDict(extra="forbid")

    adapter_count: int = Field(ge=1)
    trace_count: int = Field(ge=1)
    total: int = Field(ge=1)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    cells: list[MatrixCell]


@dataclass(frozen=True)
class _TraceCase:
    trace_id: str
    transformation: str
    ground_truth: GroundTruth


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
            cells.append(
                MatrixCell(
                    adapter=observed.adapter,
                    adapter_version=observed.adapter_version,
                    trace_id=case.trace_id,
                    transformation=case.transformation,
                    chunks_seen=observed.chunks_seen,
                    passed=report.passed,
                    issue_codes=[issue.code for issue in report.issues],
                )
            )
    passed = sum(cell.passed for cell in cells)
    return CompatibilityMatrix(
        adapter_count=len(adapter_names),
        trace_count=len(cases),
        total=len(cells),
        passed=passed,
        failed=len(cells) - passed,
        cells=cells,
    )

