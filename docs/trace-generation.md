# Semantics-preserving trace generation v0.1

CompatFlow 将工具调用 ground truth 与具体 SSE 表示分离。生成器读取一条规范轨迹，只使用其 ground truth 重新序列化工具调用，再由独立的线级解码器从生成事件中恢复语义。只有恢复结果与原 ground truth 完全一致的变体才会输出。

## 首批变换

| Preset | 改变内容 | 要验证的客户端假设 |
| --- | --- | --- |
| `merged_arguments` | 每个调用的参数在单个 chunk 中发送 | 客户端不依赖细粒度参数增量 |
| `character_arguments` | 参数按单个 Unicode 字符拆分 | 客户端能跨大量边界稳定拼接 JSON |
| `empty_deltas` | 参数片段之间插入空 `delta` | 客户端不会把空增量误判为结束或错误 |
| `explicit_nulls` | 后续片段显式携带空 `id`、`type` 和 `name` | 缺省字段与显式 null 的处理一致 |
| `repeated_metadata` | 每个参数片段重复调用 ID、类型和完整工具名 | 静态元数据重复不会改变调用身份 |
| `interleaved` | 多个调用的参数片段按 index 轮转交错 | 客户端按 index 而非到达顺序归并参数 |

其中 `repeated_metadata` 是候选鲁棒性关系，不主张所有重复形式都由 OpenAI 文档明确保证；实验报告需要将“规范要求”和“生态鲁棒性期望”分开统计。

## 生成语料

```bash
uv run compatflow-generate \
  corpus/canonical/single_tool_call.json \
  corpus/generated

uv run compatflow-generate \
  corpus/canonical/parallel_tool_calls.json \
  corpus/generated
```

命令使用固定 JSON 编码和固定调度顺序，相同输入会产生完全相同的文件。每条输出还记录来源轨迹、变换名、完整参数和生成器版本。默认回放服务器递归加载 `corpus/**/*.json`，因此生成后的轨迹无需额外配置即可出现在 `/v1/models` 和 `/_compatflow/traces`。

## 自校验

`decode_trace` 不读取轨迹中的 `ground_truth`，而是从所有 `choices[0].delta.tool_calls` 独立重建调用。它检查：

- 每个调用 index 的 ID 不冲突；
- 参数片段只能是字符串且最终组成 JSON 对象；
- 调用 ID 与函数名完整；
- 终止原因最终为 `tool_calls`。

Hypothesis 测试还会随机选择 1–32 的参数分片大小，验证任意这些边界都不改变双工具调用轨迹的解码语义。
