from compatflow.replay.models import TraceEvent
from compatflow.replay.sse import encode_event


def test_event_encoding_preserves_unicode_and_compacts_json() -> None:
    event = TraceEvent(data={"arguments": "上海"}, event="chunk", event_id="7", retry_ms=100)

    assert encode_event(event) == (
        'id: 7\nevent: chunk\nretry: 100\ndata: {"arguments":"上海"}\n\n'.encode()
    )


def test_done_encoding() -> None:
    assert encode_event(TraceEvent(data="[DONE]")) == b"data: [DONE]\n\n"

