import asyncio
from importlib.metadata import version
from pathlib import Path

import httpx
from openai import AsyncOpenAI

from compatflow.adapters import OpenAIPythonAdapter
from compatflow.oracle import OracleReport, evaluate
from compatflow.replay.app import create_app
from compatflow.replay.store import TraceStore


CORPUS = Path(__file__).parents[2] / "corpus"


async def run_matrix() -> list[OracleReport]:
    store = TraceStore(CORPUS)
    transport = httpx.ASGITransport(app=create_app(CORPUS))
    http_client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    client = AsyncOpenAI(
        api_key="compatflow",
        base_url="http://testserver/v1",
        http_client=http_client,
    )
    adapter = OpenAIPythonAdapter()
    reports = []
    try:
        for trace in store.list():
            observed = await adapter.observe(client, trace.trace_id)
            reports.append(evaluate(observed, trace.ground_truth))
    finally:
        await client.close()
    return reports


def test_openai_python_passes_generated_variant_matrix() -> None:
    reports = asyncio.run(run_matrix())

    assert len(reports) == 14
    assert {report.observed.adapter_version for report in reports} == {version("openai")}
    assert {
        report.observed.tool_calls[0].name for report in reports
    } == {"get_weather"}
    assert [
        {
            "trace_id": report.observed.trace_id,
            "issues": report.issues,
        }
        for report in reports
        if not report.passed
    ] == []
