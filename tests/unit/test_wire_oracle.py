from pathlib import Path

from compatflow.replay.models import Trace
from compatflow.wire_oracle import evaluate_wire


CORPUS = Path(__file__).parents[2] / "corpus"


def _trace(path: str) -> Trace:
    return Trace.model_validate_json((CORPUS / path).read_text(encoding="utf-8"))


def test_canonical_trace_is_wire_compliant() -> None:
    assert evaluate_wire(_trace("canonical/single_tool_call.json").events).passed


def test_reports_missing_type_without_calling_a_client() -> None:
    report = evaluate_wire(_trace("defects/missing_type_first_chunk.json").events)

    assert [issue.code for issue in report.issues] == ["missing_tool_call_type"]


def test_reports_parallel_index_collision() -> None:
    report = evaluate_wire(_trace("defects/parallel_index_collision.json").events)

    assert "tool_call_index_collision" in {issue.code for issue in report.issues}
