# Trace format v1.0

每个轨迹是一个独立 JSON 文件，包含可回放的 SSE 事件和与分片方式无关的语义 ground truth。

```json
{
  "schema_version": "1.0",
  "trace_id": "single_tool_call",
  "description": "One deterministic tool call",
  "events": [
    {"data": {"object": "chat.completion.chunk", "choices": []}, "delay_ms": 0},
    {"data": "[DONE]"}
  ],
  "ground_truth": {
    "tool_calls": [
      {
        "index": 0,
        "call_id": "call_1",
        "name": "get_weather",
        "arguments": {"city": "上海"}
      }
    ],
    "finish_reason": "tool_calls"
  }
}
```

## 约束

- `trace_id` 只能包含小写字母、数字、下划线和连字符；
- 必须存在且只能存在一个 `[DONE]`，并且它必须是最后一个事件；
- ground truth 中的工具 `index` 和 `call_id` 必须唯一；
- `delay_ms` 表示发送该事件前的等待时间，最大 60 秒；
- `event`、`event_id` 和 `retry_ms` 对应标准 SSE 字段；
- JSON 使用 UTF-8 原样发送，不将非 ASCII 字符转义为 `\\uXXXX`。

服务器启动时一次性验证整个目录。任何非法文件、重复 `trace_id` 或空语料目录都会阻止启动，避免实验过程中静默跳过坏样本。

