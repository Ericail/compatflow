"""Adapter for the independent official OpenAI Node SDK stream implementation."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path

from compatflow.results import AdapterFailure, ClientObservation


NODE_CLIENT_DIR = Path(__file__).parents[1] / "node_client"
NODE_SCRIPT = NODE_CLIENT_DIR / "observe.mjs"


def _sdk_version() -> str:
    lock_path = NODE_CLIENT_DIR / "package-lock.json"
    if not lock_path.is_file():
        return "unknown"
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    return payload.get("packages", {}).get("node_modules/openai", {}).get("version", "unknown")


def _failure(trace_id: str, exception_type: str, message: str) -> ClientObservation:
    return ClientObservation(
        trace_id=trace_id,
        adapter="openai-node",
        adapter_version=_sdk_version(),
        chunks_seen=0,
        finish_reason=None,
        tool_calls=[],
        failure=AdapterFailure(exception_type=exception_type, message=message),
    )


class OpenAINodeAdapter:
    """Run the Node SDK in a subprocess and validate its normalized JSON observation."""

    name = "openai-node"

    async def observe_url(
        self,
        server_url: str,
        trace_id: str,
        *,
        api_key: str = "compatflow",
        timeout: float = 10.0,
    ) -> ClientObservation:
        node = shutil.which("node")
        if node is None:
            return _failure(trace_id, "NodeNotFound", "node executable is not available")
        if not NODE_SCRIPT.is_file():
            return _failure(trace_id, "NodeScriptNotFound", f"missing script: {NODE_SCRIPT}")

        environment = os.environ.copy()
        environment["NO_PROXY"] = "127.0.0.1,localhost"
        environment["no_proxy"] = "127.0.0.1,localhost"
        process = await asyncio.create_subprocess_exec(
            node,
            str(NODE_SCRIPT),
            server_url,
            trace_id,
            api_key,
            _sdk_version(),
            cwd=NODE_CLIENT_DIR,
            env=environment,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout + 2)
        except TimeoutError:
            process.kill()
            await process.communicate()
            return _failure(trace_id, "TimeoutError", f"Node SDK exceeded {timeout:g} seconds")
        if process.returncode != 0:
            return _failure(
                trace_id,
                "NodeProcessError",
                stderr.decode(errors="replace").strip() or f"exit code {process.returncode}",
            )
        try:
            return ClientObservation.model_validate_json(stdout)
        except ValueError as error:
            return _failure(trace_id, type(error).__name__, str(error))
