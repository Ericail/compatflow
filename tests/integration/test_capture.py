import asyncio
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from compatflow.capture.models import CaptureRecord, ExperimentManifest
from compatflow.capture.recorder import record_experiment
from compatflow.capture.evaluate import evaluate_capture
from compatflow.replay.app import create_app
from compatflow.replay.models import Trace


CORPUS = Path(__file__).parents[2] / "corpus" / "canonical"


def _source_trace() -> Trace:
    return Trace.model_validate_json(
        (CORPUS / "single_tool_call.json").read_text(encoding="utf-8")
    )


def _manifest(**overrides: object) -> ExperimentManifest:
    source = _source_trace()
    values = {
        "experiment_id": "local_capture_test",
        "trace_id": "captured_single_tool_call",
        "description": "Capture the deterministic local replay server",
        "endpoint": "http://test/v1/chat/completions",
        "server": {
            "implementation": "compatflow",
            "version": "0.1.0",
            "model": "compatflow/single_tool_call",
            "version_evidence": "test fixture",
        },
        "request": {
            "model": "compatflow/single_tool_call",
            "messages": [{"role": "user", "content": "capture"}],
            "stream": True,
        },
        "ground_truth": source.ground_truth.model_dump(),
    }
    values.update(overrides)
    return ExperimentManifest.model_validate(values)


def test_records_exact_bytes_and_imports_replayable_trace() -> None:
    transport = httpx.ASGITransport(app=create_app(CORPUS))

    capture = asyncio.run(record_experiment(_manifest(), transport=transport))
    round_trip = CaptureRecord.model_validate_json(capture.model_dump_json())
    trace = round_trip.to_trace()

    assert capture.complete
    assert capture.failure is None
    assert capture.status_code == 200
    assert capture.response_headers["x-compatflow-trace"] == "single_tool_call"
    assert round_trip.response_bytes().endswith(b"data: [DONE]\n\n")
    assert trace.trace_id == "captured_single_tool_call"
    assert trace.events == _source_trace().events
    assert trace.provenance is not None
    assert trace.provenance.transformation == "captured"
    assert trace.provenance.response_sha256 == capture.response_sha256

    evaluation = asyncio.run(evaluate_capture(capture, ("openai-python",)))
    assert evaluation.response_sha256 == capture.response_sha256
    assert evaluation.wire_expectation_met
    assert evaluation.matrix.total == 1
    assert evaluation.matrix.unexpected == 0


def test_manifest_rejects_secrets_and_non_streaming_requests() -> None:
    with pytest.raises(ValidationError, match="authentication headers"):
        _manifest(safe_headers={"Authorization": "secret"})
    with pytest.raises(ValidationError, match="embed credentials"):
        _manifest(endpoint="http://user:secret@test/v1/chat/completions")

    request = dict(_manifest().request)
    request["stream"] = False
    with pytest.raises(ValidationError, match="stream=true"):
        _manifest(request=request)


def test_transport_failure_retains_a_valid_partial_capture() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("server unavailable", request=request)

    capture = asyncio.run(
        record_experiment(_manifest(), transport=httpx.MockTransport(fail))
    )

    assert not capture.complete
    assert capture.status_code is None
    assert capture.response_bytes() == b""
    assert capture.failure is not None
    assert capture.failure.exception_type == "ConnectError"
    with pytest.raises(ValueError, match="partial capture"):
        capture.to_trace()
