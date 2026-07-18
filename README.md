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

## 两周可行性门槛

两周 MVP 依次完成：

- 可精确回放 SSE 的 Mock Server；
- OpenAI Python、LiteLLM、LangChain 三个客户端适配器；
- 至少 20 条手工轨迹和 6 类语义保持变换；
- 基于 ground truth 的语义预言；
- 一个基础失败缩减器；
- 复现至少 3 个公开问题，并发现至少 1 个此前未报告的客户端差异。

如果最后两项均未满足，则停止扩展服务端矩阵，重新评估论文问题，而不是继续堆功能。

## 计划中的目录

```text
src/compatflow/
  adapters/      # 客户端 SDK 适配器
  replay/        # SSE 回放与真实流记录
  generator/     # 轨迹生成及语义保持变换
  oracle/        # 协议与语义预言
  reducer/       # 最小失败用例缩减
tests/           # 单元测试、已知缺陷和生成式测试
docs/            # 研究范围、相关工作和实验记录
```

## 开发环境

项目计划使用 Python 3.12、FastAPI、httpx、pytest、Hypothesis 和 Pydantic。当前提交只冻结研究问题与仓库边界，下一步才实现回放服务器。

