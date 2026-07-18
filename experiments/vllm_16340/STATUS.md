# Execution status

Status on 2026-07-19: **protocol ready, version reproduction not executed**.

The current Codex workspace has Python and Node.js but no `docker`, `nvidia-smi` or visible GPU. Running the affected manifest against `127.0.0.1:8000` produced a valid partial capture with:

- `complete=false`;
- `status_code=null`;
- `failure.exception_type=ConnectError`;
- zero response bytes and the SHA-256 of an empty body;
- no imported Trace.

The partial artifact is intentionally under ignored `results/raw/` and is not research evidence for or against the upstream bug. The next valid state transition requires running the two declared server refs on a CUDA host, retaining `collect_env.py`, and evaluating both non-empty response hashes.
