import json
from pathlib import Path

from fastapi.testclient import TestClient

from compatflow.replay.app import create_app


CORPUS = Path(__file__).parents[2] / "corpus" / "canonical"


def client() -> TestClient:
    return TestClient(create_app(CORPUS))


def test_health_and_models_catalog() -> None:
    api = client()

    assert api.get("/healthz").json()["traces"] == 2
    models = api.get("/v1/models").json()
    assert {model["id"] for model in models["data"]} == {
        "compatflow/parallel_tool_calls",
        "compatflow/single_tool_call",
    }


def test_replays_exact_stream_and_reconstructs_arguments() -> None:
    response = client().post(
        "/v1/chat/completions",
        json={"model": "compatflow/single_tool_call", "messages": [], "stream": True},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-compatflow-trace"] == "single_tool_call"

    payloads = [line[6:] for line in response.text.splitlines() if line.startswith("data: ")]
    assert payloads[-1] == "[DONE]"
    chunks = [json.loads(payload) for payload in payloads[:-1]]

    argument_fragments = []
    for chunk in chunks:
        for tool_call in chunk["choices"][0]["delta"].get("tool_calls", []):
            argument_fragments.append(tool_call.get("function", {}).get("arguments", ""))
    assert json.loads("".join(argument_fragments)) == {"city": "上海"}
    assert chunks[-1]["choices"][0]["finish_reason"] == "tool_calls"


def test_trace_header_overrides_model() -> None:
    response = client().post(
        "/v1/chat/completions",
        headers={"X-CompatFlow-Trace": "single_tool_call"},
        json={"model": "ignored", "messages": [], "stream": True},
    )

    assert response.status_code == 200


def test_rejects_non_streaming_and_unknown_trace() -> None:
    api = client()

    non_streaming = api.post(
        "/v1/chat/completions",
        json={"model": "compatflow/single_tool_call", "stream": False},
    )
    assert non_streaming.status_code == 400
    assert non_streaming.json()["error"]["param"] == "stream"

    unknown = api.post(
        "/v1/chat/completions",
        json={"model": "compatflow/missing", "stream": True},
    )
    assert unknown.status_code == 404
