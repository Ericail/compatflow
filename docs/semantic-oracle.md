# Semantic oracle v0.1

CompatFlow 不比较 SSE 字节是否完全相同，而是比较客户端 SDK 消费完整条流后恢复出的工具调用语义。因此，改变 chunk 边界、空增量或 JSON 参数切分位置时，只要最终结果相同，Oracle 就应判定通过。

## 观察模型

每个客户端适配器统一输出 `ClientObservation`：

- `adapter` 与 `adapter_version`：客户端及其精确版本；
- `chunks_seen`：SDK 实际交付给适配器的 chunk 数；
- `finish_reason`：最终停止原因；
- `tool_calls`：按 `index` 重建的调用 ID、函数名、原始参数字符串及解析后的 JSON；
- `failure`：SDK 解析、传输或迭代异常的结构化记录。

保留 `raw_arguments` 和 `parse_error` 是为了区分“参数语义不同”和“客户端恢复出的字符串根本不是合法 JSON”。异常不会终止整个实验进程，后续矩阵可以继续运行其他轨迹和客户端。

## 当前判定规则

Oracle 将观察结果与轨迹中的 `ground_truth` 比较，并报告稳定的 issue code：

| Issue code | 含义 |
| --- | --- |
| `adapter_failure` | SDK 未能完整消费流 |
| `finish_reason_mismatch` | 停止原因不同 |
| `missing_tool_call` | ground truth 中的调用未恢复 |
| `unexpected_tool_call` | 客户端额外恢复了调用 |
| `duplicate_tool_call_index` | 多个调用占用同一个 index |
| `call_id_mismatch` | 调用 ID 不同或缺失 |
| `name_mismatch` | 函数名不同或缺失 |
| `invalid_arguments_json` | 拼接后的参数不是合法 JSON |
| `arguments_mismatch` | 参数 JSON 的结构或值不同 |

对象键顺序不影响结果；数组顺序和 JSON 值类型会影响结果。例如 `1` 与 `1.0` 在当前严格模式下不同，避免 Python 的宽松相等规则掩盖跨客户端类型变化。

## 当前边界

v0.1 只评估 Chat Completions 的 choice `0` 和 function tool calls。文本内容、token usage、logprobs、Responses API 以及多个 choices 暂不进入 Oracle。并行工具调用由不同 `tool_call.index` 表示，将在下一批规范轨迹中验证。

