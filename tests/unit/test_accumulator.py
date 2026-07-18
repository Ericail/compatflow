from compatflow.adapters.accumulator import ToolCallAccumulator


def test_accumulates_fragments_and_idempotent_metadata() -> None:
    accumulator = ToolCallAccumulator()
    accumulator.add(
        index=0,
        call_id="call_1",
        name="get_weather",
        arguments='{"city":',
    )
    accumulator.add(
        index=0,
        call_id="call_1",
        name="get_weather",
        arguments='"上海"}',
    )

    result = accumulator.build()[0]

    assert result.name == "get_weather"
    assert result.arguments == {"city": "上海"}


def test_accepts_fragmented_or_cumulative_names() -> None:
    fragmented = ToolCallAccumulator()
    fragmented.add(index=0, call_id="call_1", name="get_", arguments="{")
    fragmented.add(index=0, call_id=None, name="weather", arguments="}")
    cumulative = ToolCallAccumulator()
    cumulative.add(index=0, call_id="call_1", name="get_", arguments="{")
    cumulative.add(index=0, call_id=None, name="get_weather", arguments="}")

    assert fragmented.build()[0].name == "get_weather"
    assert cumulative.build()[0].name == "get_weather"

