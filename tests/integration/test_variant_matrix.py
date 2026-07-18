import asyncio
import socket
from importlib.metadata import version
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

import pytest
import uvicorn

from compatflow.matrix import run_matrix
from compatflow.replay.app import create_app


CORPUS = Path(__file__).parents[2] / "corpus"


@pytest.fixture(scope="module")
def replay_server_url():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(create_app(CORPUS), log_level="error", lifespan="off")
    )
    thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    deadline = monotonic() + 5
    while not server.started and monotonic() < deadline:
        sleep(0.01)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=2)
        pytest.fail("replay server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)
    listener.close()


def test_two_client_variant_matrix(replay_server_url: str) -> None:
    report = asyncio.run(run_matrix(replay_server_url, ("openai-python", "litellm")))

    assert report.adapter_count == 2
    assert report.trace_count == 14
    assert report.total == 28
    assert report.passed == 28
    assert report.failed == 0
    assert {cell.adapter_version for cell in report.cells if cell.adapter == "openai-python"} == {
        version("openai")
    }
    assert {cell.adapter_version for cell in report.cells if cell.adapter == "litellm"} == {
        version("litellm")
    }
    chunk_counts = {
        (cell.adapter, cell.trace_id): cell.chunks_seen
        for cell in report.cells
    }
    assert chunk_counts[("openai-python", "parallel_tool_calls__empty_deltas")] == 22
    assert chunk_counts[("litellm", "parallel_tool_calls__empty_deltas")] == 12
    assert chunk_counts[("openai-python", "single_tool_call__empty_deltas")] == 8
    assert chunk_counts[("litellm", "single_tool_call__empty_deltas")] == 5
