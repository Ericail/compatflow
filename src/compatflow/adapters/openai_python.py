"""Adapter for the official asynchronous OpenAI Python SDK."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib.metadata import version
from typing import Any

import httpx
from openai import AsyncOpenAI

from compatflow.results import AdapterFailure, ClientObservation, ObservedToolCall


@dataclass
class _PartialToolCall:
    index: int
    call_id: str | None = None
    name_parts: list[str] = field(default_factory=list)
    argument_parts: list[str] = field(default_factory=list)

    def add(self, delta: Any) -> None:
        if delta.id:
            self.call_id = delta.id
        if delta.function is None:
            return
        if delta.function.name:
            current_name = "".join(self.name_parts)
            if delta.function.name != current_name:
                self.name_parts.append(delta.function.name)
        if delta.function.arguments is not None:
            self.argument_parts.append(delta.function.arguments)

    def build(self) -> ObservedToolCall:
        raw_arguments = "".join(self.argument_parts)
        try:
            arguments = json.loads(raw_arguments)
            parse_error = None
        except (json.JSONDecodeError, TypeError) as error:
            arguments = None
            parse_error = str(error)
        return ObservedToolCall(
            index=self.index,
            call_id=self.call_id,
            name="".join(self.name_parts) or None,
            arguments=arguments,
            raw_arguments=raw_arguments,
            parse_error=parse_error,
        )


class OpenAIPythonAdapter:
    """Consume a trace through openai-python and normalize its final semantics."""

    name = "openai-python"

    async def observe(self, client: AsyncOpenAI, trace_id: str) -> ClientObservation:
        chunks_seen = 0
        finish_reason: str | None = None
        partial_calls: dict[int, _PartialToolCall] = {}
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
                        partial = partial_calls.setdefault(
                            delta.index,
                            _PartialToolCall(index=delta.index),
                        )
                        partial.add(delta)
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
            tool_calls=[partial_calls[index].build() for index in sorted(partial_calls)],
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
