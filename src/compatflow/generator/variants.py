"""Deterministic trace variants for representation-invariance testing."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from compatflow.generator.semantics import TraceSemanticError, decode_trace
from compatflow.replay.models import ToolCallTruth, Trace, TraceEvent, TraceProvenance


@dataclass(frozen=True)
class VariantSpec:
    """One reproducible strategy for serializing fixed tool-call semantics."""

    name: str
    fragment_size: int | None
    empty_between: bool = False
    continuation_metadata: Literal["minimal", "null", "repeat"] = "minimal"
    schedule: Literal["sequential", "interleaved"] = "sequential"

    def __post_init__(self) -> None:
        if re.fullmatch(r"[a-z0-9][a-z0-9_]*", self.name) is None:
            raise ValueError("variant name must contain lowercase letters, digits, and underscores")
        if self.fragment_size is not None and self.fragment_size < 1:
            raise ValueError("fragment_size must be positive or None")


DEFAULT_VARIANTS = (
    VariantSpec(name="merged_arguments", fragment_size=None),
    VariantSpec(name="character_arguments", fragment_size=1),
    VariantSpec(name="empty_deltas", fragment_size=4, empty_between=True),
    VariantSpec(name="explicit_nulls", fragment_size=4, continuation_metadata="null"),
    VariantSpec(name="repeated_metadata", fragment_size=4, continuation_metadata="repeat"),
    VariantSpec(name="interleaved", fragment_size=4, schedule="interleaved"),
)


@dataclass(frozen=True)
class _Emission:
    call: ToolCallTruth
    fragment: str
    first: bool


def _fragments(value: str, size: int | None) -> list[str]:
    if size is None:
        return [value]
    return [value[start : start + size] for start in range(0, len(value), size)]


def _emissions(trace: Trace, spec: VariantSpec) -> list[_Emission]:
    groups: list[list[_Emission]] = []
    for call in sorted(trace.ground_truth.tool_calls, key=lambda item: item.index):
        arguments = json.dumps(call.arguments, ensure_ascii=False, separators=(",", ":"))
        groups.append(
            [
                _Emission(call=call, fragment=fragment, first=position == 0)
                for position, fragment in enumerate(_fragments(arguments, spec.fragment_size))
            ]
        )
    if spec.schedule == "sequential":
        return [emission for group in groups for emission in group]
    return [
        group[position]
        for position in range(max(len(group) for group in groups))
        for group in groups
        if position < len(group)
    ]


def _tool_delta(emission: _Emission, metadata: str) -> dict[str, Any]:
    function: dict[str, Any] = {"arguments": emission.fragment}
    payload: dict[str, Any] = {"index": emission.call.index, "function": function}
    if emission.first or metadata == "repeat":
        payload.update({"id": emission.call.call_id, "type": "function"})
        function["name"] = emission.call.name
    elif metadata == "null":
        payload.update({"id": None, "type": None})
        function["name"] = None
    return payload


def _chunk(trace_id: str, delta: dict[str, Any], finish_reason: str | None = None) -> dict:
    return {
        "id": f"chatcmpl-compatflow-{trace_id}",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": f"compatflow/{trace_id}",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }


def generate_variant(source: Trace, spec: VariantSpec) -> Trace:
    """Reserialize ground truth according to a variant and verify wire semantics."""

    trace_id = f"{source.trace_id}__{spec.name}"
    events: list[TraceEvent] = []
    for position, emission in enumerate(_emissions(source, spec)):
        if spec.empty_between and position:
            events.append(TraceEvent(data=_chunk(trace_id, {})))
        delta: dict[str, Any] = {
            "tool_calls": [_tool_delta(emission, spec.continuation_metadata)]
        }
        if position == 0:
            delta["role"] = "assistant"
        events.append(TraceEvent(data=_chunk(trace_id, delta)))
    events.extend(
        [
            TraceEvent(data=_chunk(trace_id, {}, finish_reason="tool_calls")),
            TraceEvent(data="[DONE]"),
        ]
    )
    variant = Trace(
        trace_id=trace_id,
        description=f"{source.description} Variant: {spec.name}.",
        events=events,
        ground_truth=source.ground_truth.model_copy(deep=True),
        provenance=TraceProvenance(
            source_trace_id=source.trace_id,
            transformation=spec.name,
            parameters=asdict(spec),
        ),
    )
    if decode_trace(variant) != source.ground_truth:
        raise TraceSemanticError(f"variant {trace_id} changed decoded tool-call semantics")
    return variant
