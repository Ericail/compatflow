"""Wire-level baseline checks for streamed Chat Completions tool calls."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from compatflow.replay.models import TraceEvent


class WireIssue(BaseModel):
    """One structural defect visible without consuming the stream through an SDK."""

    model_config = ConfigDict(extra="forbid")

    code: str
    event_index: int
    path: str
    message: str
    observed: Any = None


class WireReport(BaseModel):
    """Deterministic structural baseline for a sequence of SSE data events."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    issues: list[WireIssue]


def evaluate_wire(events: list[TraceEvent]) -> WireReport:
    """Check required first-delta identity fields and index consistency."""

    issues: list[WireIssue] = []
    identities: dict[int, str | None] = {}
    for event_index, event in enumerate(events):
        if event.data == "[DONE]":
            continue
        choices = event.data.get("choices")
        if not isinstance(choices, list):
            continue
        for choice_index, choice in enumerate(choices):
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta")
            if not isinstance(delta, dict):
                continue
            tool_calls = delta.get("tool_calls")
            if not isinstance(tool_calls, list):
                continue
            for call_position, call in enumerate(tool_calls):
                base_path = (
                    f"events[{event_index}].choices[{choice_index}]"
                    f".delta.tool_calls[{call_position}]"
                )
                if not isinstance(call, dict):
                    issues.append(
                        WireIssue(
                            code="invalid_tool_call_delta",
                            event_index=event_index,
                            path=base_path,
                            message="tool-call delta must be an object",
                            observed=call,
                        )
                    )
                    continue
                index = call.get("index")
                if not isinstance(index, int) or isinstance(index, bool) or index < 0:
                    issues.append(
                        WireIssue(
                            code="missing_tool_call_index",
                            event_index=event_index,
                            path=f"{base_path}.index",
                            message="tool-call delta requires a non-negative integer index",
                            observed=index,
                        )
                    )
                    continue
                call_id = call.get("id")
                first_for_index = index not in identities
                if first_for_index:
                    if not isinstance(call_id, str) or not call_id:
                        issues.append(
                            WireIssue(
                                code="missing_tool_call_id",
                                event_index=event_index,
                                path=f"{base_path}.id",
                                message="first delta for an index requires a non-empty id",
                                observed=call_id,
                            )
                        )
                    if call.get("type") != "function":
                        issues.append(
                            WireIssue(
                                code="missing_tool_call_type",
                                event_index=event_index,
                                path=f"{base_path}.type",
                                message="first delta for an index requires type='function'",
                                observed=call.get("type"),
                            )
                        )
                    identities[index] = call_id if isinstance(call_id, str) else None
                elif isinstance(call_id, str) and call_id != identities[index]:
                    issues.append(
                        WireIssue(
                            code="tool_call_index_collision",
                            event_index=event_index,
                            path=f"{base_path}.index",
                            message="one index is associated with multiple call IDs",
                            observed={"index": index, "ids": [identities[index], call_id]},
                        )
                    )
    return WireReport(passed=not issues, issues=issues)
