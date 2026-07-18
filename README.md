# CompatFlow

CompatFlow 是一个面向 LLM 流式工具调用的跨实现兼容性研究项目。它测试同一条语义等价的 SSE 工具调用流，经不同 OpenAI-compatible 服务端产生、再由不同客户端 SDK 消费后，是否恢复出相同的工具调用结果。

当前阶段只研究：

- `POST /v1/chat/completions`
- `stream=true`
- `tool_calls`

暂不研究 Responses API、模型回答质量、吞吐性能、多模态和鉴权。

## 研究假设

OpenAPI/JSON Schema 合法并不等于生态兼容。流式分片边界、事件顺序、并行调用索引和可选字段的差异，可能让真实客户端丢失参数、合并工具调用、异常退出或永久等待。

CompatFlow 的候选创新点不是再造一套 Schema 检查，而是：

1. 构建“推理服务端 × 客户端 SDK”的兼容性矩阵；
2. 生成语义不变、分片方式不同的流式轨迹；
3. 用客户端最终恢复的工具调用语义作为测试预言；
4. 自动缩减失败轨迹，生成可提交给上游的最小复现案例；
5. 跨多个版本测量兼容性缺陷与回归。

详细定义见：

- [研究范围](docs/research-scope.md)
- [相关工作与差异表](docs/related-work.md)
- [轨迹格式 v1.0](docs/trace-format.md)
- [语义 Oracle v0.1](docs/semantic-oracle.md)
- [语义保持轨迹生成 v0.1](docs/trace-generation.md)
- [三客户端兼容性矩阵 v0.2](docs/client-matrix.md)
- [已知缺陷类别种子](docs/defect-seeds.md)
- [失败缩减器](docs/failure-reduction.md)

## 当前实现：生成、回放、跨客户端判定与失败缩减

仓库从 `corpus/canonical/*.json` 加载经过严格验证的轨迹，提供 OpenAI-compatible 流式端点，并通过官方 OpenAI Python SDK 消费流。适配器把 SDK 输出归一化为与分片边界无关的观察结果，Oracle 再对照轨迹 ground truth 给出机器可读的通过/失败报告。

```bash
uv sync --extra dev
uv run compatflow-replay
```

另一个终端请求内置轨迹：

```bash
curl -N http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "compatflow/single_tool_call",
    "messages": [{"role": "user", "content": "上海天气如何？"}],
    "stream": true
  }'
```

运行官方 OpenAI Python SDK 的端到端兼容性检查：

```bash
uv run compatflow-check single_tool_call
```

命令以 JSON 输出 `passed`、逐字段差异、SDK 版本、消费的 chunk 数以及重建后的工具调用。通过时退出码为 `0`，不兼容或 SDK 异常时退出码为 `1`，可直接接入 CI 和后续实验矩阵。

用 OpenAI Python、LiteLLM 和 OpenAI Node 运行全部 18 条轨迹：

```bash
uv run compatflow-matrix
```

矩阵输出 54 个单元格的客户端版本、变换类别、chunk 数、实际 issue codes 和预期结果。已知负向轨迹按预期失败不会让命令失败；只有出现非预期通过或非预期失败时退出码才为 `1`。单条检查也可以用 `--adapter litellm` 或 `--adapter openai-node` 切换客户端。

从单工具和并行工具规范轨迹生成六类确定性变体：

```bash
uv run compatflow-generate corpus/canonical/single_tool_call.json corpus/generated
uv run compatflow-generate corpus/canonical/parallel_tool_calls.json corpus/generated
```

当前仓库包含 2 条人工规范轨迹、12 条自动生成变体和 4 条缺陷类别种子。生成器使用独立线级解码器自校验 ground truth，并由 Hypothesis 随机覆盖额外的参数切分边界。

将一个失败轨迹缩减为保持完整 Oracle 报告的 1-minimal 事件序列：

```bash
uv run compatflow-reduce \
  corpus/defects/raw_tool_call_content.json \
  /tmp/raw_tool_call_content.min.json \
  --adapter openai-python
```

缩减器支持三个适配器，输出原始/缩减事件数、尝试次数和失败签名。若轨迹在所选客户端上不失败，或输出已存在且未传 `--force`，命令会拒绝生成误导性结果。

也可以使用 `X-CompatFlow-Trace: single_tool_call` 请求头选择轨迹，这时 `model` 会被忽略。可用端点包括：

- `GET /healthz`：服务和语料健康状态；
- `GET /v1/models`：以 OpenAI 模型列表格式返回轨迹；
- `GET /_compatflow/traces`：返回轨迹说明、事件数和 ground truth；
- `POST /v1/chat/completions`：精确回放 SSE 事件。

自定义语料目录可以通过 `COMPATFLOW_CORPUS_DIR` 指定，监听地址和端口分别由 `COMPATFLOW_HOST`、`COMPATFLOW_PORT` 控制。

运行测试和静态检查：

```bash
uv run pytest
uv run ruff check .
```

## 两周可行性门槛

两周 MVP 依次完成：

- 可精确回放 SSE 的 Mock Server；
- OpenAI Python、LiteLLM、OpenAI Node 三个客户端适配器；
- 至少 20 条手工轨迹和 6 类语义保持变换；
- 基于 ground truth 的语义预言；
- 一个基础失败缩减器；
- 复现至少 3 个公开问题，并发现至少 1 个此前未报告的客户端差异。

如果最后两项均未满足，则停止扩展服务端矩阵，重新评估论文问题，而不是继续堆功能。

## 计划中的目录

```text
src/compatflow/
  adapters/      # 三个客户端 SDK 适配器
  node_client/   # 独立 Node SDK 观察进程
  replay/        # SSE 回放
  generator/     # 轨迹生成及语义保持变换
  oracle.py      # 语义预言
  reducer.py     # 失败保持的 ddmin 缩减
tests/           # 单元测试、已知缺陷和生成式测试
docs/            # 研究范围、相关工作和实验记录
```

## 开发环境

项目使用 Python 3.12、Node.js、FastAPI、OpenAI Python、OpenAI Node、LiteLLM、httpx、pytest、Hypothesis 和 Pydantic。当前固定基线为 46/54 个单元格语义通过、8/54 个按预期失败、54/54 个预期吻合。下一阶段接入真实 vLLM/SGLang 版本并做纵向版本实验。
