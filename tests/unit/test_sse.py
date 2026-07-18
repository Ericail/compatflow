from compatflow.replay.models import TraceEvent
from compatflow.replay.sse import decode_events, encode_event


def test_event_encoding_preserves_unicode_and_compacts_json() -> None:
    event = TraceEvent(data={"arguments": "上海"}, event="chunk", event_id="7", retry_ms=100)

    assert encode_event(event) == (
        'id: 7\nevent: chunk\nretry: 100\ndata: {"arguments":"上海"}\n\n'.encode()
    )


def test_done_encoding() -> None:
    assert encode_event(TraceEvent(data="[DONE]")) == b"data: [DONE]\n\n"


def test_decodes_crlf_multiline_data_and_sse_fields() -> None:
    payload = (
        b": keepalive\r\n"
        b"id: 7\r\n"
        b"event: chunk\r\n"
        b"retry: 100\r\n"
        b'data: {"choices":\r\n'
        b"data: []}\r\n\r\n"
        b"data: [DONE]\r\n\r\n"
    )

    assert decode_events(payload) == [
        TraceEvent(
            data={"choices": []},
            event="chunk",
            event_id="7",
            retry_ms=100,
        ),
        TraceEvent(data="[DONE]"),
    ]
