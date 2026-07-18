"""Filesystem-backed corpus loading with strict validation."""

from __future__ import annotations

import json
from pathlib import Path

from compatflow.replay.models import Trace


class TraceNotFoundError(KeyError):
    """Raised when a requested trace ID is not present in the corpus."""


class TraceStore:
    """Immutable in-memory view of validated JSON trace files."""

    def __init__(self, corpus_dir: Path) -> None:
        self.corpus_dir = corpus_dir
        self._traces = self._load(corpus_dir)

    @staticmethod
    def _load(corpus_dir: Path) -> dict[str, Trace]:
        if not corpus_dir.is_dir():
            raise FileNotFoundError(f"trace corpus directory does not exist: {corpus_dir}")

        traces: dict[str, Trace] = {}
        for path in sorted(corpus_dir.glob("*.json")):
            with path.open(encoding="utf-8") as handle:
                trace = Trace.model_validate(json.load(handle))
            if trace.trace_id in traces:
                raise ValueError(f"duplicate trace_id {trace.trace_id!r} in {path}")
            traces[trace.trace_id] = trace

        if not traces:
            raise ValueError(f"trace corpus is empty: {corpus_dir}")
        return traces

    def get(self, trace_id: str) -> Trace:
        try:
            return self._traces[trace_id]
        except KeyError as exc:
            raise TraceNotFoundError(trace_id) from exc

    def list(self) -> list[Trace]:
        return list(self._traces.values())

