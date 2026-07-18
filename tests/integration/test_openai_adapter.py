import asyncio
from pathlib import Path

import httpx
from openai import AsyncOpenAI

from compatflow.adapters import OpenAIPythonAdapter
from compatflow.oracle import evaluate
from compatflow.replay.app import create_app
from compatflow.replay.store import TraceStore


CORPUS = Path(__file__).parents[2] / "corpus" / "canonical"


async def run_adapter() -> tuple:
    app = create_app(CORPUS)
    transport = httpx.ASGITransport(app=app)
    http_client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    client = AsyncOpenAI(
        api_key="compatflow",
        base_url="http://testserver/v1",
        http_client=http_client,
    )
    try:
        observed = await OpenAIPythonAdapter().observe(client, "single_tool_call")
    finally:
        await client.close()
    expected = TraceStore(CORPUS).get("single_tool_call").ground_truth
    return observed, evaluate(observed, expected)


def test_official_openai_sdk_reconstructs_canonical_trace() -> None:
    observed, report = asyncio.run(run_adapter())

    assert observed.failure is None
    assert observed.chunks_seen == 4
    assert observed.tool_calls[0].arguments == {"city": "上海"}
    assert report.passed

