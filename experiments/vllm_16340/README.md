# vLLM #16340 affected/fixed experiment

This pair separates wire conformance from client-visible semantics. The upstream report used vLLM `0.8.3` and found that a named `tool_choice` omitted `type:function` in the first streamed tool delta. Upstream PR #17340 was squash-merged as `05a4324` on 2025-05-12 and explicitly initialized the first-delta identity fields.

## Required hardware

- Linux host with Docker and NVIDIA Container Toolkit;
- one CUDA GPU capable of serving `Qwen/Qwen2.5-7B-Instruct-AWQ`;
- enough disk for both images and model weights.

Run the `server.launch_command` from `affected.json`, then record:

```bash
uv run compatflow-record \
  experiments/vllm_16340/affected.json \
  results/raw/vllm_16340_affected.capture.json \
  --trace-output results/traces/vllm_16340_affected.json
```

Build the fixed image from upstream commit `05a4324`, run the command in `fixed.json`, and record it on port 8001:

```bash
git clone https://github.com/vllm-project/vllm.git /tmp/vllm-05a4324
git -C /tmp/vllm-05a4324 checkout 05a4324
docker build -f /tmp/vllm-05a4324/docker/Dockerfile \
  -t compatflow/vllm:05a4324 /tmp/vllm-05a4324

uv run compatflow-record \
  experiments/vllm_16340/fixed.json \
  results/raw/vllm_16340_fixed.capture.json \
  --trace-output results/traces/vllm_16340_fixed.json
```

Retain `collect_env.py` output beside each capture. A completed capture is still only a candidate reproduction until its response hash, wire report, semantic matrix and environment evidence are archived together.
