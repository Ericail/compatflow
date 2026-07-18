"""Adapter for LiteLLM's asynchronous OpenAI-compatible streaming client."""

from __future__ import annotations

import os
from importlib.metadata import version
from typing import Any

import httpx

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "true")
from openai import AsyncOpenAI

from compatflow.adapters.accumulator import ToolCallAccumulator
from compatflow.results import AdapterFailure, ClientObservation


def _get(value: Any, field: str) -> Any:
    if isinstance(value, dict):
        return value.get(field)
    return getattr(value, field, None)


class LiteLLMAdapter:
    """Consume a replay trace through LiteLLM and normalize reconstructed semantics."""

    name = "litellm"

    async def observe_url(
        self,
        server_url: str,
        trace_id: str,
        *,
        api_key: str = "compatflow",
        timeout: float = 10.0,
    ) -> ClientObservation:
        chunks_seen = 0
        finish_reason: str | None = None
        accumulator = ToolCallAccumulator()
        failure: AdapterFailure | None = None
        http_client = httpx.AsyncClient(timeout=timeout, trust_env=False)
        openai_client = AsyncOpenAI(
            api_key=api_key,
            base_url=f"{server_url.rstrip('/')}/v1",
            timeout=timeout,
            max_retries=0,
            http_client=http_client,
        )
        try:
            from litellm import acompletion

            stream = await acompletion(
                model=f"openai/compatflow/{trace_id}",
                api_base=f"{server_url.rstrip('/')}/v1",
                api_key=api_key,
                messages=[{"role": "user", "content": f"Replay trace {trace_id}"}],
                stream=True,
                timeout=timeout,
                max_retries=0,
                client=openai_client,
            )
            async for chunk in stream:
                chunks_seen += 1
                for choice in _get(chunk, "choices") or []:
                    if _get(choice, "index") != 0:
                        continue
                    if _get(choice, "finish_reason") is not None:
                        finish_reason = _get(choice, "finish_reason")
                    delta = _get(choice, "delta")
                    for tool_call in _get(delta, "tool_calls") or []:
                        function = _get(tool_call, "function")
                        accumulator.add(
                            index=_get(tool_call, "index"),
                            call_id=_get(tool_call, "id"),
                            name=_get(function, "name"),
                            arguments=_get(function, "arguments"),
                        )
        except Exception as error:
            failure = AdapterFailure(
                exception_type=type(error).__name__,
                message=str(error),
            )
        finally:
            await openai_client.close()

        return ClientObservation(
            trace_id=trace_id,
            adapter=self.name,
            adapter_version=version("litellm"),
            chunks_seen=chunks_seen,
            finish_reason=finish_reason,
            tool_calls=accumulator.build(),
            failure=failure,
        )
