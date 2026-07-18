"""FastAPI application that deterministically replays stored SSE traces."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from compatflow import __version__
from compatflow.replay.models import Trace
from compatflow.replay.sse import encode_event
from compatflow.replay.store import TraceNotFoundError, TraceRepository, TraceStore


def _default_corpus_dir() -> Path:
    configured = os.getenv("COMPATFLOW_CORPUS_DIR")
    return Path(configured) if configured else Path.cwd() / "corpus"


def _error(message: str, *, status_code: int, param: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "message": message,
                "type": "invalid_request_error",
                "param": param,
                "code": None,
            }
        },
    )


def _select_trace_id(body: dict[str, Any], header_value: str | None) -> str | None:
    if header_value:
        return header_value
    model = body.get("model")
    if not isinstance(model, str):
        return None
    prefix = "compatflow/"
    return model[len(prefix) :] if model.startswith(prefix) else model


async def _replay(trace: Trace) -> AsyncIterator[bytes]:
    for event in trace.events:
        if event.delay_ms:
            await asyncio.sleep(event.delay_ms / 1_000)
        yield encode_event(event)


def create_app(
    corpus_dir: Path | None = None,
    *,
    store: TraceRepository | None = None,
) -> FastAPI:
    """Create a replay app bound to one validated corpus directory."""

    if corpus_dir is not None and store is not None:
        raise ValueError("provide corpus_dir or store, not both")
    trace_store = store or TraceStore(corpus_dir or _default_corpus_dir())
    app = FastAPI(title="CompatFlow Replay Server", version=__version__)
    app.state.trace_store = trace_store

    @app.get("/healthz")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "traces": len(trace_store.list()), "version": __version__}

    @app.get("/v1/models")
    async def models() -> dict[str, Any]:
        return {
            "object": "list",
            "data": [
                {
                    "id": f"compatflow/{trace.trace_id}",
                    "object": "model",
                    "created": 0,
                    "owned_by": "compatflow",
                }
                for trace in trace_store.list()
            ],
        }

    @app.get("/_compatflow/traces")
    async def trace_catalog() -> dict[str, Any]:
        return {
            "traces": [
                {
                    "trace_id": trace.trace_id,
                    "description": trace.description,
                    "event_count": len(trace.events),
                    "ground_truth": trace.ground_truth.model_dump(),
                    "provenance": (
                        trace.provenance.model_dump() if trace.provenance is not None else None
                    ),
                    "expectation": trace.expectation.model_dump(),
                }
                for trace in trace_store.list()
            ]
        }

    @app.post("/v1/chat/completions")
    async def chat_completions(
        request: Request,
        x_compatflow_trace: str | None = Header(default=None),
    ) -> Response:
        try:
            body = await request.json()
        except ValueError:
            return _error("request body must be valid JSON", status_code=400)
        if not isinstance(body, dict):
            return _error("request body must be a JSON object", status_code=400)
        if body.get("stream") is not True:
            return _error("CompatFlow replay requires stream=true", status_code=400, param="stream")

        trace_id = _select_trace_id(body, x_compatflow_trace)
        if trace_id is None:
            return _error(
                "provide model='compatflow/<trace_id>' or X-CompatFlow-Trace",
                status_code=400,
                param="model",
            )
        try:
            trace = trace_store.get(trace_id)
        except TraceNotFoundError:
            return _error(f"unknown trace: {trace_id}", status_code=404, param="model")

        return StreamingResponse(
            _replay(trace),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-CompatFlow-Trace": trace.trace_id,
                "X-Accel-Buffering": "no",
            },
        )

    return app
