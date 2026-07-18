"""SSE wire encoding for replay events."""

from __future__ import annotations

import json

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

