# Defect-class seeds v0.1

本目录中的缺陷种子用于验证客户端影响分类，不把“手工蒸馏的线格式”冒充为“已在指定上游版本完成复现”。只有未来在固定服务端版本上抓取原始响应、保存环境与请求，并验证结果后，才能将状态升级为 version reproduction。

| Trace | 类型 | 来源 | 当前三客户端结果 |
| --- | --- | --- | --- |
| `defect_missing_type_first_chunk` | 公开缺陷类别 | [vLLM #16340](https://github.com/vllm-project/vllm/issues/16340) | 三者语义兼容；说明所测客户端宽容，不否定严格客户端所受影响 |
| `defect_parallel_index_collision` | 公开缺陷类别 | [SGLang #25073](https://github.com/sgl-project/sglang/issues/25073) | 三者均合并调用并产生语义失败 |
| `defect_raw_tool_call_content` | 公开缺陷类别 | [vLLM #31871](https://github.com/vllm-project/vllm/issues/31871) | 三者均看不到结构化调用，且结束原因错误 |
| `defect_missing_tool_call_index` | CompatFlow 合成差异种子 | 无外部归因 | LiteLLM 恢复成功；OpenAI Python/Node 失败 |

## 纳入标准

一个公开问题只有在端点、流式模式和工具调用语义都位于研究范围内时，才可作为来源。种子必须保留最小必要异常，并给出独立 ground truth 与预期 issue codes。某个客户端若有明确不同的稳定行为，使用 `adapter_overrides` 固化，而不是把差异隐藏在测试代码里。

## 已排除的近似问题

- vLLM #19650 是中间 chunk 省略 `finish_reason: null`，不等于终止原因缺失；因此没有用它支持“缺少终止事件”的种子。
- SGLang #12653 针对 Responses API，而第一阶段明确只纳入 Chat Completions；因此未加入语料。

这两项排除记录用于防止后续写作把相似字段名误写成直接复现。
