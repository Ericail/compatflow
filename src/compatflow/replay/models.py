"""Validated models for reproducible streaming traces."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToolCallTruth(BaseModel):
    """Canonical tool-call semantics expected after a client consumes a trace."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    call_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    arguments: dict[str, Any]


class GroundTruth(BaseModel):
    """Expected semantic result represented independently from SSE chunking."""

    model_config = ConfigDict(extra="forbid")

    tool_calls: list[ToolCallTruth] = Field(min_length=1)
    finish_reason: Literal["tool_calls"] = "tool_calls"

    @model_validator(mode="after")
    def unique_tool_calls(self) -> GroundTruth:
        indexes = [call.index for call in self.tool_calls]
        call_ids = [call.call_id for call in self.tool_calls]
        if len(indexes) != len(set(indexes)):
            raise ValueError("ground-truth tool-call indexes must be unique")
        if len(call_ids) != len(set(call_ids)):
            raise ValueError("ground-truth call IDs must be unique")
        return self


class TraceEvent(BaseModel):
    """One Server-Sent Event and its optional delivery metadata."""

    model_config = ConfigDict(extra="forbid")

    data: dict[str, Any] | Literal["[DONE]"]
    delay_ms: int = Field(default=0, ge=0, le=60_000)
    event: str | None = None
    event_id: str | None = None
    retry_ms: int | None = Field(default=None, ge=0)


class TraceProvenance(BaseModel):
    """Reproducible origin metadata for a generated trace."""

    model_config = ConfigDict(extra="forbid")

    source_trace_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    transformation: str = Field(pattern=r"^[a-z0-9][a-z0-9_]*$")
    parameters: dict[str, Any]
    generator_version: Literal["0.1"] = "0.1"


class Trace(BaseModel):
    """A replayable wire trace paired with a semantic oracle."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    trace_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    description: str = Field(min_length=1)
    events: list[TraceEvent] = Field(min_length=1)
    ground_truth: GroundTruth
    provenance: TraceProvenance | None = None

    @model_validator(mode="after")
    def done_is_terminal(self) -> Trace:
        done_positions = [i for i, event in enumerate(self.events) if event.data == "[DONE]"]
        if done_positions != [len(self.events) - 1]:
            raise ValueError("a trace must contain exactly one terminal [DONE] event")
        return self
