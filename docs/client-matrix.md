# Client compatibility matrix v0.1

CompatFlow 当前把同一组 14 条轨迹分别交给两个真实 Python 客户端消费：官方 OpenAI Python SDK 与 LiteLLM。每个客户端适配器只读取该客户端暴露的流式 chunk，再通过共享累加器生成统一 `ClientObservation`，最后由同一个语义 Oracle 判定。

## 客户端

| Adapter | 当前锁定版本 | 调用路径 |
| --- | --- | --- |
| `openai-python` | `2.46.0` | `AsyncOpenAI.chat.completions.create(stream=True)` |
| `litellm` | `1.92.0` | `litellm.acompletion(stream=True)`，使用 `openai/` 模型前缀 |

锁文件是版本事实来源；表中的版本随依赖升级更新。LiteLLM 配置为使用包内模型价格表，避免实验启动时访问远程价格数据。两个适配器访问回放服务器时均忽略环境代理。

## 运行矩阵

先启动回放服务器：

```bash
uv run compatflow-replay
```

另一个终端运行全部客户端与轨迹：

```bash
uv run compatflow-matrix
```

只运行指定客户端：

```bash
uv run compatflow-matrix --adapter litellm
```

输出是确定性 JSON，包含：

- `adapter_count`、`trace_count` 与总单元格数；
- 通过和失败数量；
- 每个单元格的客户端及版本、轨迹、变换类别、SDK 收到的 chunk 数和 issue codes。

只要任一单元格失败，命令退出码就是 `1`，可直接用于 CI。完整测试通过真实的本地 TCP/HTTP 服务运行双客户端 28 个单元格，不使用模型 API 或付费密钥。

## 当前基线结果

在 OpenAI Python `2.46.0` 与 LiteLLM `1.92.0` 上，28 个单元格的最终工具调用语义全部通过。不过两者暴露给调用方的 chunk 数并不总是相同：

| 轨迹 | OpenAI Python | LiteLLM |
| --- | ---: | ---: |
| `single_tool_call__empty_deltas` | 8 | 5 |
| `parallel_tool_calls__empty_deltas` | 22 | 12 |

LiteLLM 的流包装路径过滤了空增量，而官方 SDK 将其交给调用方；其他当前变体的 chunk 数一致。由于调用数量、身份、名称、参数和结束原因仍完全相同，语义 Oracle 将其正确归为无害表示差异，而不是兼容性缺陷。这个结果已固化为版本化回归断言，升级任一客户端后会重新验证。

## 解释边界

当前两个客户端的 OpenAI-compatible 路径都直接或间接使用官方 OpenAI Python 库，因此它们不是完全独立的协议解析器。这个矩阵首先验证 CompatFlow 的跨客户端实验基础设施；下一客户端应选择具有独立流处理实现的框架，例如 LangChain 的不同封装路径或 JavaScript SDK。
