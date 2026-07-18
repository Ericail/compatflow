# 相关工作与课题差异

检索更新时间：2026-07-18。当前的新颖性主张是“跨服务端—真实客户端、以流式工具调用最终语义为预言的行为兼容性测试”，而不是“第一个 OpenAI API 合规测试工具”。提交论文前必须重新检索并收窄主张。

## 对照表

| 工作 | 已覆盖内容 | 与本课题的重合 | 当前缺口 / CompatFlow 的区别 | 来源 |
| --- | --- | --- | --- | --- |
| Open Responses specification and compliance suite | 定义多提供商接口、item 状态机、语义流事件；提供 Schema、基本 streaming、tool calling 等合规测试 | 高：已有流式语义与运行时测试，不能声称“首次测试流式 API” | 现有套件主要判断端点对规范的接受与响应结构；CompatFlow 测量同一流在多个真实客户端中的最终工具语义，并系统变换分片和并行交错 | [Repository](https://github.com/openresponses/openresponses), [Compliance tests](https://www.openresponses.org/compliance) |
| Llama Stack OpenAI parity / conformance | 使用 `oasdiff` 比较 Llama Stack 与 OpenAI 的 OpenAPI 描述，并修复 Schema 差异 | 中：同属 API 兼容性 | 关注单实现的描述文件和结构一致性；不构建跨服务端—客户端运行时矩阵 | [Issue #4619](https://github.com/llamastack/llama-stack/issues/4619) |
| Schemathesis | 从 OpenAPI/GraphQL Schema 派生属性测试，对有状态 Web API 进行语义感知模糊测试 | 中：可作为生成式 API 测试基线 | 通用 Web API 工具，不建模 LLM 工具参数的增量拼接、并行调用身份及客户端消费语义 | [Paper](https://arxiv.org/abs/2112.10328), [Repository](https://github.com/schemathesis/schemathesis) |
| COMFORT | 对多个 JavaScript 引擎做规范驱动的差分测试并发现一致性缺陷 | 低：方法论上可作为跨实现合规测试参考 | 研究对象是 ECMAScript 引擎；CompatFlow 面向网络流协议和客户端解析结果，没有可直接复制的确定性执行输出 | [Paper](https://arxiv.org/abs/2104.07460) |
| AEX | 为 JSON 型 LLM API 设计请求—响应证明，讨论工具调用、流式和错误语义，并带局部合规测试 | 低至中：同样触及 LLM API 流式语义 | 目标是来源证明和完整性验证，不测多个兼容实现及客户端解析差异 | [Paper](https://arxiv.org/abs/2603.14283) |
| vLLM streaming tool-call issues | 已出现首个工具分片缺少 `type:function`、usage 位置、finish reason 等回归 | 高：提供真实缺陷类别和种子轨迹 | 单项目 issue 和回归测试，没有统一生成方法、跨客户端影响分析及跨版本实证 | [#16340](https://github.com/vllm-project/vllm/issues/16340), [#19650](https://github.com/vllm-project/vllm/issues/19650) |
| SGLang streaming compatibility issues | Responses 流格式差异、缺失 tool index、重复同名工具导致 index 合并等 | 高：提供真实缺陷类别和种子轨迹 | 单项目、单场景修复；CompatFlow 应发现未进入其回归集的新组合并测量真实客户端后果 | [#12653](https://github.com/sgl-project/sglang/issues/12653), [#25073](https://github.com/sgl-project/sglang/issues/25073) |
| llama.cpp streaming compatibility issues | 首个参数片段处理、SSE 必需字段和中途 500 等问题 | 高：直接验证问题的现实性 | 单实现维护记录；缺乏跨 SDK 的统一语义预言和自动失败缩减 | [#22722](https://github.com/ggml-org/llama.cpp/issues/22722), [#20607](https://github.com/ggml-org/llama.cpp/issues/20607) |

## 与最近邻工作的核心分界

CompatFlow 必须同时满足以下四项，才具有独立研究价值：

1. **关系型兼容性：** 测试对象是服务端实现与客户端实现的组合，不是孤立服务端。
2. **行为级预言：** 以客户端最终重建的工具调用语义为结果，不止校验 Schema。
3. **语义保持变换：** 对同一 ground truth 系统改变合法分片与交错方式，验证实现对表示变化的不变性。
4. **研究级验证：** 与 Open Responses 合规测试及普通随机/示例测试比较，报告独立缺陷、误报、发现效率、版本回归和维护者确认。

如果实现最终只包含固定样例、字段检查和兼容性排行榜，应将其定位为工程工具，而不能宣称方法型论文贡献。

## 检索记录

初步检索覆盖 arXiv、ACM Digital Library、IEEE Xplore、OpenReview 与 GitHub，核心组合包括：

- `"OpenAI-compatible" AND (conformance OR compatibility OR fuzzing)`
- `"LLM API" AND (differential testing OR conformance testing)`
- `streaming AND tool calls AND compatibility`
- `vLLM SGLang llama.cpp Ollama API benchmark`
- `stateful fuzzing OpenAI compatible API`

截至本次检索，未发现完整覆盖“多推理服务 × 多真实客户端 × 流式工具调用语义变换 × 自动缩减”的正式论文；这是有限公开检索结论，不是无人研究的证明。

