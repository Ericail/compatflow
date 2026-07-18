"""Validated manifests and immutable live-capture artifacts."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from compatflow.replay.models import (
    CaptureProvenance,
    GroundTruth,
    Trace,
    TraceExpectation,
)
from compatflow.replay.sse import decode_events


def canonical_request_bytes(request: dict[str, Any]) -> bytes:
    """Serialize a request deterministically for provenance hashing."""

    return json.dumps(
        request,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class ServerSpec(BaseModel):
    """Declared server identity plus evidence needed to audit it later."""

    model_config = ConfigDict(extra="forbid")

    implementation: str = Field(min_length=1)
    version: str = Field(min_length=1)
    model: str = Field(min_length=1)
    image: str | None = None
    source_ref: str | None = None
    version_evidence: str = Field(min_length=1)
    launch_command: list[str] = Field(default_factory=list)


class WireExpectation(BaseModel):
    """Expected outcome of the deliberately simpler wire-format baseline."""

    model_config = ConfigDict(extra="forbid")

    outcome: Literal["compliant", "noncompliant"] = "compliant"
    issue_codes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_issue_codes(self) -> WireExpectation:
        if self.outcome == "compliant" and self.issue_codes:
            raise ValueError("compliant wire results cannot require issue codes")
        if self.outcome == "noncompliant" and not self.issue_codes:
            raise ValueError("noncompliant wire results require issue codes")
        return self


class ExperimentManifest(BaseModel):
    """One replayable request against one declared server version."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    experiment_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    trace_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    description: str = Field(min_length=1)
    endpoint: str
    server: ServerSpec
    request: dict[str, Any]
    ground_truth: GroundTruth
    expectation: TraceExpectation = Field(default_factory=TraceExpectation)
    wire_expectation: WireExpectation = Field(default_factory=WireExpectation)
    safe_headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=300, gt=0, le=3_600)
    max_response_bytes: int = Field(default=50_000_000, ge=1, le=500_000_000)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("endpoint must be an absolute HTTP(S) URL")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("endpoint cannot embed credentials")
        return value

    @field_validator("safe_headers")
    @classmethod
    def reject_secret_headers(cls, value: dict[str, str]) -> dict[str, str]:
        forbidden = {"authorization", "proxy-authorization", "cookie", "x-api-key"}
        secret_names = forbidden & {name.lower() for name in value}
        if secret_names:
            raise ValueError(
                "authentication headers must come from --api-key-env, not the manifest"
            )
        return value

    @model_validator(mode="after")
    def validate_request(self) -> ExperimentManifest:
        if self.request.get("stream") is not True:
            raise ValueError("experiment request must set stream=true")
        if not isinstance(self.request.get("model"), str):
            raise ValueError("experiment request must include a model string")
        return self


class CapturedChunk(BaseModel):
    """One byte chunk observed from the HTTP transport with relative timing."""

    model_config = ConfigDict(extra="forbid")

    offset_ms: int = Field(ge=0)
    data_base64: str = Field(min_length=1)

    def data(self) -> bytes:
        try:
            return base64.b64decode(self.data_base64, validate=True)
        except ValueError as error:
            raise ValueError("captured chunk is not valid base64") from error


class CaptureFailure(BaseModel):
    """Transport or size-limit failure retained alongside any partial bytes."""

    model_config = ConfigDict(extra="forbid")

    exception_type: str = Field(min_length=1)
    message: str


class CaptureRecord(BaseModel):
    """Exact response bytes, timing, request identity and declared server provenance."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    capture_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    captured_at: datetime
    manifest: ExperimentManifest
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status_code: int | None = Field(default=None, ge=100, le=599)
    response_headers: dict[str, str] = Field(default_factory=dict)
    chunks: list[CapturedChunk] = Field(default_factory=list)
    response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    elapsed_ms: int = Field(ge=0)
    complete: bool
    failure: CaptureFailure | None = None
    recorder_environment: dict[str, str]

    @model_validator(mode="after")
    def validate_hashes_and_completion(self) -> CaptureRecord:
        request_digest = hashlib.sha256(
            canonical_request_bytes(self.manifest.request)
        ).hexdigest()
        if request_digest != self.request_sha256:
            raise ValueError("request_sha256 does not match the manifest request")
        response_digest = hashlib.sha256(self.response_bytes()).hexdigest()
        if response_digest != self.response_sha256:
            raise ValueError("response_sha256 does not match captured chunks")
        if self.complete == (self.failure is not None):
            raise ValueError("complete captures cannot have a failure and partial captures must")
        return self

    def response_bytes(self) -> bytes:
        return b"".join(chunk.data() for chunk in self.chunks)

    def to_trace(self) -> Trace:
        """Convert a complete successful SSE capture into a replayable Trace."""

        if not self.complete:
            raise ValueError("partial capture cannot be converted to a trace")
        if self.status_code is None or not 200 <= self.status_code < 300:
            raise ValueError(f"HTTP status {self.status_code!r} cannot be converted to a trace")
        events = decode_events(self.response_bytes())
        request_model = self.manifest.request["model"]
        return Trace(
            trace_id=self.manifest.trace_id,
            description=self.manifest.description,
            events=events,
            ground_truth=self.manifest.ground_truth,
            provenance=CaptureProvenance(
                capture_id=self.capture_id,
                experiment_id=self.manifest.experiment_id,
                server_implementation=self.manifest.server.implementation,
                server_version=self.manifest.server.version,
                server_source_ref=self.manifest.server.source_ref,
                server_image=self.manifest.server.image,
                endpoint=self.manifest.endpoint,
                model=request_model,
                captured_at=self.captured_at.isoformat(),
                request_sha256=self.request_sha256,
                response_sha256=self.response_sha256,
            ),
            expectation=self.manifest.expectation,
        )
