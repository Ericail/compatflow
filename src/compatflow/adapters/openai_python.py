"""Adapter for the official asynchronous OpenAI Python SDK."""

from __future__ import annotations

from importlib.metadata import version

import httpx
from openai import AsyncOpenAI

from compatflow.adapters.accumulator import ToolCallAccumulator
from compatflow.results import AdapterFailure, ClientObservation


class OpenAIPythonAdapter:
    """Consume a trace through openai-python and normalize its final semantics."""

    name = "openai-python"

    async def observe(self, client: AsyncOpenAI, trace_id: str) -> ClientObservation:
        chunks_seen = 0
        finish_reason: str | None = None
        accumulator = ToolCallAccumulator()
        failure: AdapterFailure | None = None
        try:
            stream = await client.chat.completions.create(
                model=f"compatflow/{trace_id}",
                messages=[{"role": "user", "content": f"Replay trace {trace_id}"}],
                stream=True,
            )
            async for chunk in stream:
                chunks_seen += 1
                for choice in chunk.choices:
                    if choice.index != 0:
                        continue
                    if choice.finish_reason is not None:
                        finish_reason = choice.finish_reason
                    for delta in choice.delta.tool_calls or []:
                        accumulator.add(
                            index=delta.index,
                            call_id=delta.id,
                            name=delta.function.name if delta.function else None,
                            arguments=delta.function.arguments if delta.function else None,
                        )
        except Exception as error:
            failure = AdapterFailure(
                exception_type=type(error).__name__,
                message=str(error),
            )

        return ClientObservation(
            trace_id=trace_id,
            adapter=self.name,
            adapter_version=version("openai"),
            chunks_seen=chunks_seen,
            finish_reason=finish_reason,
            tool_calls=accumulator.build(),
            failure=failure,
        )

    async def observe_url(
        self,
        server_url: str,
        trace_id: str,
        *,
        api_key: str = "compatflow",
        timeout: float = 10.0,
    ) -> ClientObservation:
        """Connect to a replay server and observe one trace."""

        transport_client = httpx.AsyncClient(timeout=timeout, trust_env=False)
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=f"{server_url.rstrip('/')}/v1",
            timeout=timeout,
            http_client=transport_client,
        )
        try:
            return await self.observe(client, trace_id)
        finally:
            await client.close()
