from compatflow.oracle import evaluate
from compatflow.replay.models import GroundTruth, ToolCallTruth
from compatflow.results import ClientObservation, ObservedToolCall


def truth() -> GroundTruth:
    return GroundTruth(
        tool_calls=[
            ToolCallTruth(
                index=0,
                call_id="call_1",
                name="get_weather",
                arguments={"city": "上海"},
            )
        ]
    )


def observation(**overrides: object) -> ClientObservation:
    values = {
        "trace_id": "test_trace",
        "adapter": "test-client",
        "adapter_version": "1.0",
        "chunks_seen": 3,
        "finish_reason": "tool_calls",
        "tool_calls": [
            ObservedToolCall(
                index=0,
                call_id="call_1",
                name="get_weather",
                arguments={"city": "上海"},
                raw_arguments='{"city":"上海"}',
            )
        ],
    }
    values.update(overrides)
    return ClientObservation.model_validate(values)


def test_matching_observation_passes() -> None:
    report = evaluate(observation(), truth())

    assert report.passed
    assert report.issues == []


def test_reports_precise_semantic_mismatches() -> None:
    mismatched_call = ObservedToolCall(
        index=0,
        call_id="wrong",
        name="get_weather",
        arguments={"city": "北京"},
        raw_arguments='{"city":"北京"}',
    )

    report = evaluate(observation(finish_reason="stop", tool_calls=[mismatched_call]), truth())

    assert not report.passed
    assert {issue.code for issue in report.issues} == {
        "finish_reason_mismatch",
        "call_id_mismatch",
        "arguments_mismatch",
    }


def test_json_comparison_is_type_strict() -> None:
    expected = GroundTruth(
        tool_calls=[ToolCallTruth(index=0, call_id="call_1", name="tool", arguments={"x": 1})]
    )
    actual = ObservedToolCall(
        index=0,
        call_id="call_1",
        name="tool",
        arguments={"x": 1.0},
        raw_arguments='{"x":1.0}',
    )

    report = evaluate(observation(tool_calls=[actual]), expected)

    assert [issue.code for issue in report.issues] == ["arguments_mismatch"]


def test_reports_invalid_json_and_duplicate_indexes() -> None:
    invalid = ObservedToolCall(
        index=0,
        call_id="call_1",
        name="get_weather",
        arguments=None,
        raw_arguments='{"city":',
        parse_error="unexpected end of input",
    )

    report = evaluate(observation(tool_calls=[invalid, invalid]), truth())

    assert {issue.code for issue in report.issues} == {
        "duplicate_tool_call_index",
        "invalid_arguments_json",
    }


def test_call_id_presence_policy_accepts_any_non_empty_identifier() -> None:
    expected = GroundTruth(
        tool_calls=[
            ToolCallTruth(
                index=0,
                call_id_policy="present",
                name="get_weather",
                arguments={"city": "上海"},
            )
        ]
    )

    assert evaluate(observation(), expected).passed
    missing = observation(
        tool_calls=[
            ObservedToolCall(
                index=0,
                call_id=None,
                name="get_weather",
                arguments={"city": "上海"},
                raw_arguments='{"city":"上海"}',
            )
        ]
    )
    assert [issue.code for issue in evaluate(missing, expected).issues] == ["call_id_missing"]
