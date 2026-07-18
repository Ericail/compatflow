"""Wire-level semantic decoder used to validate generated traces."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from compatflow.replay.models import GroundTruth, ToolCallTruth, Trace


class TraceSemanticError(ValueError):
    """Raised when a trace cannot be decoded into complete tool-call semantics."""


@dataclass
class _DecodedCall:
    index: int
    call_id: str | None = None
    name: str = ""
    argument_parts: list[str] = field(default_factory=list)

    def add(self, payload: dict[str, Any]) -> None:
        call_id = payload.get("id")
        if call_id is not None:
            if self.call_id is not None and self.call_id != call_id:
                raise TraceSemanticError(f"conflicting call IDs at index {self.index}")
            self.call_id = call_id
        function = payload.get("function")
        if not isinstance(function, dict):
            return
        name = function.get("name")
        if name is not None and name != self.name:
            self.name += name
        arguments = function.get("arguments")
        if arguments is not None:
            if not isinstance(arguments, str):
                raise TraceSemanticError(f"arguments at index {self.index} must be strings")
            self.argument_parts.append(arguments)

    def build(self) -> ToolCallTruth:
        if self.call_id is None or not self.name:
            raise TraceSemanticError(f"incomplete metadata at tool-call index {self.index}")
        raw_arguments = "".join(self.argument_parts)
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError as error:
            raise TraceSemanticError(
                f"invalid arguments JSON at tool-call index {self.index}: {error}"
            ) from error
        if not isinstance(arguments, dict):
            raise TraceSemanticError(f"arguments at index {self.index} must decode to an object")
        return ToolCallTruth(
            index=self.index,
            call_id=self.call_id,
            name=self.name,
            arguments=arguments,
        )


def decode_trace(trace: Trace) -> GroundTruth:
    """Decode tool-call semantics from SSE payloads without using stored ground truth."""

    calls: dict[int, _DecodedCall] = {}
    finish_reason: str | None = None
    for event in trace.events:
        if event.data == "[DONE]":
            continue
        choices = event.data.get("choices")
        if not isinstance(choices, list):
            raise TraceSemanticError("every data event must contain a choices list")
        for choice in choices:
            if not isinstance(choice, dict) or choice.get("index") != 0:
                continue
            if choice.get("finish_reason") is not None:
                finish_reason = choice["finish_reason"]
            delta = choice.get("delta")
            if delta is None:
                continue
            if not isinstance(delta, dict):
                raise TraceSemanticError("choice delta must be an object or null")
            tool_calls = delta.get("tool_calls") or []
            if not isinstance(tool_calls, list):
                raise TraceSemanticError("delta.tool_calls must be a list")
            for payload in tool_calls:
                if not isinstance(payload, dict) or not isinstance(payload.get("index"), int):
                    raise TraceSemanticError("every tool-call delta must have an integer index")
                index = payload["index"]
                calls.setdefault(index, _DecodedCall(index=index)).add(payload)

    if finish_reason != "tool_calls":
        raise TraceSemanticError(f"expected terminal finish_reason='tool_calls', got {finish_reason!r}")
    return GroundTruth(
        tool_calls=[calls[index].build() for index in sorted(calls)],
        finish_reason="tool_calls",
    )

