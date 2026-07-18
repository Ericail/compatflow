# Failure reduction v0.1

`compatflow-reduce` 对 `[DONE]` 之前的 SSE 事件运行 delta debugging。每个候选轨迹都由所选真实客户端重新消费，并重新经过语义 Oracle。只有完整 Oracle issue 对象（包括 code、path、expected 与 observed）全部不变时，删除才被接受。

```bash
uv run compatflow-reduce INPUT.json OUTPUT.json --adapter openai-python
```

也可选择 `litellm` 或 `openai-node`。输出轨迹是相对于“删除整个 SSE 事件”操作的 1-minimal 结果：继续删除任一剩余事件都不能保持同一失败报告。它不保证字节级全局最小，也暂不缩减单个事件内部的 JSON 字段或字符串片段。

固定回归测试把一个带两个无关空增量的真实 SDK 失败样本从 4 个事件缩到 2 个，并保持 `finish_reason_mismatch` 与 `missing_tool_call` 的 observed 值不变。后续实验应增加字段级和参数片段级缩减，并报告缩减率、Oracle 调用次数与时间。
