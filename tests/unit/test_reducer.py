import asyncio
from pathlib import Path

from compatflow.reducer import minimize_events, reduce_trace
from compatflow.replay.models import Trace, TraceEvent


CORPUS = Path(__file__).parents[2] / "corpus"


def test_ddmin_removes_irrelevant_events() -> None:
    trace = Trace.model_validate_json(
        (CORPUS / "canonical" / "single_tool_call.json").read_text(encoding="utf-8")
    )
    required = trace.events[0]

    async def contains_required(candidate: Trace) -> bool:
        return required in candidate.events

    reduced, attempts = asyncio.run(minimize_events(trace, contains_required))

    assert reduced.events == [required, trace.events[-1]]
    assert attempts > 0


def test_real_sdk_reduction_preserves_complete_failure_signature() -> None:
    trace = Trace.model_validate_json(
        (CORPUS / "defects" / "raw_tool_call_content.json").read_text(encoding="utf-8")
    )
    noisy_events = [
        TraceEvent(data={"choices": [{"index": 0, "delta": {}, "finish_reason": None}]}),
        *trace.events[:-1],
        TraceEvent(data={"choices": [{"index": 0, "delta": {}, "finish_reason": None}]}),
        trace.events[-1],
    ]
    noisy_trace = trace.model_copy(update={"events": noisy_events})

    result = asyncio.run(reduce_trace(noisy_trace, "openai-python"))

    assert result.failure_signature == ["finish_reason_mismatch", "missing_tool_call"]
    assert result.original_event_count == 4
    assert result.reduced_event_count == 2
    assert result.trace.events[-1].data == "[DONE]"
