"""Temporary single-trace TCP replay server for SDK experiments."""

from __future__ import annotations

import socket
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock, Thread
from time import monotonic, sleep

import uvicorn

from compatflow.replay.app import create_app
from compatflow.replay.models import Trace
from compatflow.replay.store import TraceNotFoundError


class TraceSlot:
    """Thread-safe mutable single-trace repository for sequential experiments."""

    def __init__(self, trace: Trace) -> None:
        self._trace = trace
        self._lock = Lock()

    def replace(self, trace: Trace) -> None:
        with self._lock:
            self._trace = trace

    def get(self, trace_id: str) -> Trace:
        with self._lock:
            trace = self._trace
        if trace.trace_id != trace_id:
            raise TraceNotFoundError(trace_id)
        return trace

    def list(self) -> list[Trace]:
        with self._lock:
            return [self._trace]


@contextmanager
def replay_server(trace: Trace) -> Iterator[tuple[str, TraceSlot]]:
    """Serve one replaceable trace on an ephemeral localhost TCP port."""

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    slot = TraceSlot(trace)
    server = uvicorn.Server(
        uvicorn.Config(create_app(store=slot), log_level="error", lifespan="off")
    )
    thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    deadline = monotonic() + 5
    while not server.started and monotonic() < deadline:
        sleep(0.01)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=2)
        listener.close()
        raise RuntimeError("temporary replay server did not start")
    try:
        yield f"http://127.0.0.1:{port}", slot
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
