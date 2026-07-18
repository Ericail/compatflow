"""Semantic oracle for comparing client observations with trace ground truth."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from compatflow.replay.models import GroundTruth
from compatflow.results import ClientObservation


class OracleIssue(BaseModel):
    """One precise reason an observation differs from ground truth."""

    model_config = ConfigDict(extra="forbid")

    code: str
    path: str
    message: str
    expected: Any = None
    observed: Any = None


class OracleReport(BaseModel):
    """Machine-readable verdict for one adapter and one trace."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    issues: list[OracleIssue]
    expected: GroundTruth
    observed: ClientObservation


def _json_equal(left: Any, right: Any) -> bool:
    """Compare JSON values without conflating bool/int or int/float."""

    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _json_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _json_equal(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    return left == right


def evaluate(observed: ClientObservation, expected: GroundTruth) -> OracleReport:
    """Evaluate semantic equivalence independently of SSE chunk boundaries."""

    issues: list[OracleIssue] = []
    if observed.failure is not None:
        issues.append(
            OracleIssue(
                code="adapter_failure",
                path="failure",
                message="client SDK did not consume the complete stream",
                observed=observed.failure.model_dump(),
            )
        )

    if observed.finish_reason != expected.finish_reason:
        issues.append(
            OracleIssue(
                code="finish_reason_mismatch",
                path="finish_reason",
                message="finish reason differs from ground truth",
                expected=expected.finish_reason,
                observed=observed.finish_reason,
            )
        )

    expected_by_index = {call.index: call for call in expected.tool_calls}
    observed_by_index = {}
    for call in observed.tool_calls:
        if call.index in observed_by_index:
            issues.append(
                OracleIssue(
                    code="duplicate_tool_call_index",
                    path=f"tool_calls[{call.index}]",
                    message="client reconstructed multiple tool calls with the same index",
                    observed=[
                        observed_by_index[call.index].model_dump(),
                        call.model_dump(),
                    ],
                )
            )
            continue
        observed_by_index[call.index] = call
    for index in sorted(expected_by_index.keys() - observed_by_index.keys()):
        issues.append(
            OracleIssue(
                code="missing_tool_call",
                path=f"tool_calls[{index}]",
                message="expected tool call was not reconstructed",
                expected=expected_by_index[index].model_dump(),
            )
        )
    for index in sorted(observed_by_index.keys() - expected_by_index.keys()):
        issues.append(
            OracleIssue(
                code="unexpected_tool_call",
                path=f"tool_calls[{index}]",
                message="client reconstructed an unexpected tool call",
                observed=observed_by_index[index].model_dump(),
            )
        )

    for index in sorted(expected_by_index.keys() & observed_by_index.keys()):
        truth = expected_by_index[index]
        actual = observed_by_index[index]
        if truth.call_id_policy == "exact" and truth.call_id != actual.call_id:
            issues.append(
                OracleIssue(
                    code="call_id_mismatch",
                    path=f"tool_calls[{index}].call_id",
                    message="tool call call_id differs from ground truth",
                    expected=truth.call_id,
                    observed=actual.call_id,
                )
            )
        elif truth.call_id_policy == "present" and not actual.call_id:
            issues.append(
                OracleIssue(
                    code="call_id_missing",
                    path=f"tool_calls[{index}].call_id",
                    message="tool call must expose a non-empty call_id",
                    expected="non-empty string",
                    observed=actual.call_id,
                )
            )
        if truth.name != actual.name:
            issues.append(
                OracleIssue(
                    code="name_mismatch",
                    path=f"tool_calls[{index}].name",
                    message="tool call name differs from ground truth",
                    expected=truth.name,
                    observed=actual.name,
                )
            )
        if actual.parse_error is not None:
            issues.append(
                OracleIssue(
                    code="invalid_arguments_json",
                    path=f"tool_calls[{index}].arguments",
                    message="client reconstructed arguments that are not valid JSON",
                    expected=truth.arguments,
                    observed=actual.raw_arguments,
                )
            )
        elif not _json_equal(truth.arguments, actual.arguments):
            issues.append(
                OracleIssue(
                    code="arguments_mismatch",
                    path=f"tool_calls[{index}].arguments",
                    message="tool arguments differ from ground truth",
                    expected=truth.arguments,
                    observed=actual.arguments,
                )
            )

    return OracleReport(
        passed=not issues,
        issues=issues,
        expected=expected,
        observed=observed,
    )
