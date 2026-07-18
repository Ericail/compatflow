"""Streaming HTTP recorder that preserves exact response bytes and chunk timing."""

from __future__ import annotations

import base64
import hashlib
import platform
from datetime import UTC, datetime
from time import perf_counter

import httpx

from compatflow import __version__
from compatflow.capture.models import (
    CaptureFailure,
    CaptureRecord,
    CapturedChunk,
    ExperimentManifest,
    canonical_request_bytes,
)


_SAFE_RESPONSE_HEADERS = {
    "content-type",
    "date",
    "server",
    "transfer-encoding",
    "x-correlation-id",
    "x-compatflow-trace",
    "x-request-id",
}


async def record_experiment(
    manifest: ExperimentManifest,
    *,
    api_key: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> CaptureRecord:
    """Record one request without persisting authentication material."""

    headers = {
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
        **manifest.safe_headers,
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    chunks: list[CapturedChunk] = []
    status_code: int | None = None
    response_headers: dict[str, str] = {}
    failure: CaptureFailure | None = None
    complete = False
    total_bytes = 0
    started = perf_counter()
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(manifest.timeout_seconds),
            trust_env=False,
            transport=transport,
        ) as client:
            async with client.stream(
                "POST",
                manifest.endpoint,
                headers=headers,
                json=manifest.request,
            ) as response:
                status_code = response.status_code
                response_headers = {
                    name.lower(): value
                    for name, value in response.headers.items()
                    if name.lower() in _SAFE_RESPONSE_HEADERS
                }
                async for data in response.aiter_raw():
                    if not data:
                        continue
                    total_bytes += len(data)
                    if total_bytes > manifest.max_response_bytes:
                        raise ValueError(
                            f"response exceeded {manifest.max_response_bytes} byte limit"
                        )
                    chunks.append(
                        CapturedChunk(
                            offset_ms=round((perf_counter() - started) * 1_000),
                            data_base64=base64.b64encode(data).decode("ascii"),
                        )
                    )
                complete = True
    except Exception as error:
        failure = CaptureFailure(
            exception_type=type(error).__name__,
            message=str(error),
        )

    elapsed_ms = round((perf_counter() - started) * 1_000)
    response_bytes = b"".join(chunk.data() for chunk in chunks)
    captured_at = datetime.now(UTC).isoformat()
    run_stamp = datetime.now(UTC).strftime("%Y%m%dt%H%M%S%fz").lower()
    return CaptureRecord(
        capture_id=f"{manifest.experiment_id}_{run_stamp}",
        captured_at=captured_at,
        manifest=manifest,
        request_sha256=hashlib.sha256(canonical_request_bytes(manifest.request)).hexdigest(),
        status_code=status_code,
        response_headers=response_headers,
        chunks=chunks,
        response_sha256=hashlib.sha256(response_bytes).hexdigest(),
        elapsed_ms=elapsed_ms,
        complete=complete,
        failure=failure,
        recorder_environment={
            "compatflow": __version__,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "httpx": httpx.__version__,
        },
    )
