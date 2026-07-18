"""Client-independent observations produced after consuming a streamed trace."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ObservedToolCall(BaseModel):
    """One tool call as reconstructed by a client SDK adapter."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    call_id: str | None
    name: str | None
    arguments: Any | None
    raw_arguments: str
    parse_error: str | None = None


class AdapterFailure(BaseModel):
    """A structured SDK or transport failure captured by an adapter."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["sdk_error"] = "sdk_error"
    exception_type: str
    message: str


class ClientObservation(BaseModel):
    """Normalized output of one client SDK consuming one streamed trace."""

    model_config = ConfigDict(extra="forbid")

    trace_id: str
    adapter: str
    adapter_version: str
    chunks_seen: int = Field(ge=0)
    finish_reason: str | None
    tool_calls: list[ObservedToolCall]
    failure: AdapterFailure | None = None
