import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from compatflow.replay.models import Trace
from compatflow.replay.store import TraceStore


CORPUS = Path(__file__).parents[2] / "corpus" / "canonical"


def test_canonical_trace_loads_with_ground_truth() -> None:
    trace = TraceStore(CORPUS).get("single_tool_call")

    assert trace.events[-1].data == "[DONE]"
    assert trace.ground_truth.tool_calls[0].arguments == {"city": "上海"}


def test_done_must_be_unique_and_terminal() -> None:
    payload = json.loads((CORPUS / "single_tool_call.json").read_text(encoding="utf-8"))
    payload["events"].insert(0, {"data": "[DONE]"})

    with pytest.raises(ValidationError, match="exactly one terminal"):
        Trace.model_validate(payload)


def test_ground_truth_indexes_must_be_unique() -> None:
    payload = json.loads((CORPUS / "single_tool_call.json").read_text(encoding="utf-8"))
    payload["ground_truth"]["tool_calls"].append(
        {
            "index": 0,
            "call_id": "call_duplicate",
            "name": "other",
            "arguments": {},
        }
    )

    with pytest.raises(ValidationError, match="indexes must be unique"):
        Trace.model_validate(payload)

