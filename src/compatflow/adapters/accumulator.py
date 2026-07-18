"""Shared tool-call accumulation for client-specific stream adapters."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from compatflow.results import ObservedToolCall


def _merge_name(current: str, incoming: str | None) -> str:
    if not incoming or incoming == current:
        return current
    if incoming.startswith(current):
        return incoming
    return current + incoming


@dataclass
class _PartialToolCall:
    index: int
    call_id: str | None = None
    name: str = ""
    argument_parts: list[str] = field(default_factory=list)

    def add(
        self,
        *,
        call_id: str | None,
        name: str | None,
        arguments: str | None,
    ) -> None:
        if call_id:
            self.call_id = call_id
        self.name = _merge_name(self.name, name)
        if arguments is not None:
            self.argument_parts.append(arguments)

    def build(self) -> ObservedToolCall:
        raw_arguments = "".join(self.argument_parts)
        try:
            arguments = json.loads(raw_arguments)
            parse_error = None
        except (json.JSONDecodeError, TypeError) as error:
            arguments = None
            parse_error = str(error)
        return ObservedToolCall(
            index=self.index,
            call_id=self.call_id,
            name=self.name or None,
            arguments=arguments,
            raw_arguments=raw_arguments,
            parse_error=parse_error,
        )


class ToolCallAccumulator:
    """Accumulate client-exposed deltas by tool-call index."""

    def __init__(self) -> None:
        self._calls: dict[int, _PartialToolCall] = {}

    def add(
        self,
        *,
        index: int,
        call_id: str | None,
        name: str | None,
        arguments: str | None,
    ) -> None:
        partial = self._calls.setdefault(index, _PartialToolCall(index=index))
        partial.add(call_id=call_id, name=name, arguments=arguments)

    def build(self) -> list[ObservedToolCall]:
        return [self._calls[index].build() for index in sorted(self._calls)]

