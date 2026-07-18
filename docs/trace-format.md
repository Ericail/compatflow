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
  },
  "provenance": null,
  "expectation": {
    "outcome": "compatible",
    "issue_codes": [],
    "reference": null,
    "adapter_overrides": {}
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
- `expectation.outcome` 为 `compatible` 时不得要求 issue code；为 `incompatible` 时至少要求一个；
- `adapter_overrides` 可以记录某个客户端与默认预期不同的结果，用于固定跨客户端差异；
- `reference` 只链接缺陷类别来源；它本身不证明该 JSON 是对应版本的原始网络抓包。

人工规范轨迹的 `provenance` 为 `null` 或省略。自动生成轨迹必须记录 `source_trace_id`、`transformation`、完整参数和 `generator_version`，使每个实验样本都能从规范轨迹重新生成。

服务器启动时一次性验证整个目录。任何非法文件、重复 `trace_id` 或空语料目录都会阻止启动，避免实验过程中静默跳过坏样本。
