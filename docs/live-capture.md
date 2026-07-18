# Live capture and version experiments v0.1

`compatflow-record` sends one manifest-defined streaming Chat Completions request and stores an auditable capture artifact. Authentication is read from an environment variable and never written to the manifest or output.

Each capture contains:

- the complete validated experiment manifest;
- exact response bytes as ordered base64 HTTP chunks;
- millisecond offsets for transport chunks;
- canonical request SHA-256 and exact response SHA-256;
- safe response headers, HTTP status and partial-transport failures;
- recorder versions and declared server version evidence.

```bash
OPENAI_API_KEY=... uv run compatflow-record \
  experiments/vllm_16340/affected.json \
  results/raw/affected.capture.json \
  --trace-output results/traces/affected.json
```

The command rejects secrets embedded in manifests, refuses to overwrite artifacts without `--force`, and saves partial bytes when the transport fails. Trace import additionally requires a complete 2xx response, valid UTF-8/JSON SSE data and exactly one terminal `[DONE]`.

Evaluate the immutable response hash offline through all three clients:

```bash
uv run compatflow-evaluate-capture results/raw/affected.capture.json
```

This command starts an ephemeral localhost replay server, feeds the exact captured bytes to each SDK, and emits the wire report plus the semantic compatibility matrix. Repeated analysis therefore does not ask the model to generate a new response.

## Two distinct oracles

The recorder runs a deliberately simple wire baseline over the imported trace. It checks first-delta `index`, `id` and `type:function`, plus collisions between call IDs and indexes. This is separate from CompatFlow's client semantic Oracle.

For vLLM #16340, the affected expectation is:

- wire baseline: `missing_tool_call_type`;
- current three clients: semantic compatibility may still hold.

That contrast is an intended experimental result: a structural violation can be harmless for permissive clients but break strict clients. Conversely, raw tagged tool content can be structurally valid JSON while destroying application semantics. Neither oracle subsumes the other.

## Evidence levels

1. `defect-class seed`: hand-distilled response shape;
2. `capture candidate`: raw bytes from a declared version;
3. `version reproduction`: capture plus environment evidence and repeated result;
4. `confirmed defect`: reproduction accepted or fixed by upstream maintainers.

Reports and papers must use the highest level actually achieved. The current execution environment has no Docker/GPU, so the checked-in vLLM pair is a runnable protocol, not a completed version reproduction.
