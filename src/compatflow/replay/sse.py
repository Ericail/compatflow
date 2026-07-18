"""SSE wire encoding for replay events."""

from __future__ import annotations

import json
from typing import Any, Literal

from compatflow.replay.models import TraceEvent


def encode_event(event: TraceEvent) -> bytes:
    """Encode one event without altering its JSON semantics."""

    lines: list[str] = []
    if event.event_id is not None:
        lines.append(f"id: {event.event_id}")
    if event.event is not None:
        lines.append(f"event: {event.event}")
    if event.retry_ms is not None:
        lines.append(f"retry: {event.retry_ms}")

    if event.data == "[DONE]":
        payload = "[DONE]"
    else:
        payload = json.dumps(event.data, ensure_ascii=False, separators=(",", ":"))
    lines.append(f"data: {payload}")
    return ("\n".join(lines) + "\n\n").encode("utf-8")


def decode_events(payload: bytes) -> list[TraceEvent]:
    """Decode a complete UTF-8 SSE body without accepting non-JSON data events."""

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("SSE response is not valid UTF-8") from error
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    events: list[TraceEvent] = []
    for frame in normalized.split("\n\n"):
        if not frame.strip():
            continue
        data_lines: list[str] = []
        fields: dict[str, Any] = {}
        for line in frame.split("\n"):
            if not line or line.startswith(":"):
                continue
            field, separator, value = line.partition(":")
            if separator and value.startswith(" "):
                value = value[1:]
            if field == "data":
                data_lines.append(value)
            elif field == "event":
                fields["event"] = value
            elif field == "id":
                fields["event_id"] = value
            elif field == "retry":
                try:
                    fields["retry_ms"] = int(value)
                except ValueError as error:
                    raise ValueError(f"invalid SSE retry value: {value!r}") from error
        if not data_lines:
            continue
        raw_data = "\n".join(data_lines)
        if raw_data == "[DONE]":
            data: dict[str, Any] | Literal["[DONE]"] = "[DONE]"
        else:
            try:
                decoded = json.loads(raw_data)
            except json.JSONDecodeError as error:
                raise ValueError("SSE data field is not valid JSON") from error
            if not isinstance(decoded, dict):
                raise ValueError("SSE JSON data must be an object")
            data = decoded
        events.append(TraceEvent(data=data, **fields))
    if not events:
        raise ValueError("SSE response contains no data events")
    return events
