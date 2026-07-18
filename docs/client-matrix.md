# Client compatibility matrix v0.2

CompatFlow 当前把同一组 18 条轨迹分别交给三个真实客户端消费：官方 OpenAI Python SDK、LiteLLM 和官方 OpenAI Node SDK。每个客户端适配器只读取该客户端暴露的流式 chunk，再生成统一 `ClientObservation`，最后由同一个语义 Oracle 判定。

## 客户端

| Adapter | 当前锁定版本 | 调用路径 |
| --- | --- | --- |
| `openai-python` | `2.46.0` | `AsyncOpenAI.chat.completions.create(stream=True)` |
| `litellm` | `1.92.0` | `litellm.acompletion(stream=True)`，使用 `openai/` 模型前缀 |
| `openai-node` | `6.48.0` | Node `OpenAI.chat.completions.create(stream: true)` |

锁文件是版本事实来源；表中的版本随依赖升级更新。LiteLLM 配置为使用包内模型价格表，避免实验启动时访问远程价格数据。三个适配器访问回放服务器时均绕过环境代理。

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
- 语义通过/失败、预期吻合/非预期数量；
- 每个单元格的客户端及版本、轨迹、变换类别、SDK 收到的 chunk 数和 issue codes。

只有出现非预期结果时，命令退出码才是 `1`，可直接用于 CI。完整测试通过真实的本地 TCP/HTTP 服务运行三客户端 54 个单元格，不使用模型 API 或付费密钥。

## 当前基线结果

固定基线共有 46 个语义通过和 8 个语义失败；所有 54 个结果都符合版本化预期，`unexpected=0`。14 条正向轨迹在三个客户端上全部通过。不过客户端暴露给调用方的 chunk 数并不总是相同：

| 轨迹 | OpenAI Python | LiteLLM |
| --- | ---: | ---: |
| `single_tool_call__empty_deltas` | 8 | 5 |
| `parallel_tool_calls__empty_deltas` | 22 | 12 |

LiteLLM 的流包装路径过滤了空增量，而 Python 与 Node 官方 SDK 将其交给调用方；其他当前变体的 chunk 数一致。由于调用数量、身份、名称、参数和结束原因仍完全相同，语义 Oracle 将其正确归为无害表示差异，而不是兼容性缺陷。

缺陷类别种子的结果如下：

| Seed | OpenAI Python | LiteLLM | OpenAI Node |
| --- | --- | --- | --- |
| missing `type:function` | compatible | compatible | compatible |
| missing tool-call `index`（合成） | adapter failure | compatible（补为 0） | adapter failure |
| repeated calls share one index | incompatible | incompatible | incompatible |
| raw tagged content + `finish_reason=stop` | incompatible | incompatible | incompatible |

缺失 index 的结果构成当前首个跨客户端差异：LiteLLM 对单调用流进行了容错，而两个官方 SDK 路径没有产生可用的规范化结果。它是合成差异种子，不声称已在某个服务端版本上发现。其余种子只表示从公开报告蒸馏出的缺陷类别，不等于已经运行并复现对应上游软件版本；边界见 [defect-seeds.md](defect-seeds.md)。

## 解释边界

OpenAI Python 与 LiteLLM 的当前 OpenAI-compatible 路径直接或间接使用同一个 Python SDK；OpenAI Node 使用独立的 JavaScript SSE 与类型实现，并在独立子进程中运行。因此当前结果不能被描述为三个完全独立解析器。下一步是接入报告中对应的真实服务端版本，区分“类别重放”和“版本复现”。
