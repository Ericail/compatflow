"""Delta-debugging reducer for SDK-observed streaming failures."""

from __future__ import annotations

import math
from collections.abc import Awaitable, Callable

from pydantic import BaseModel, ConfigDict, Field

from compatflow.adapters import AdapterName, get_adapter
from compatflow.oracle import evaluate
from compatflow.replay.ephemeral import replay_server
from compatflow.replay.models import Trace


FailurePredicate = Callable[[Trace], Awaitable[bool]]


class ReductionResult(BaseModel):
    """A 1-minimal event sequence that preserves one complete oracle report."""

    model_config = ConfigDict(extra="forbid")

    adapter: str
    failure_signature: list[str]
    original_event_count: int = Field(ge=1)
    reduced_event_count: int = Field(ge=1)
    attempts: int = Field(ge=0)
    trace: Trace


async def minimize_events(trace: Trace, predicate: FailurePredicate) -> tuple[Trace, int]:
    """Apply ddmin to non-terminal events while preserving ``predicate``."""

    done = trace.events[-1]
    current = list(trace.events[:-1])
    attempts = 0
    granularity = 2
    while current:
        chunk_size = math.ceil(len(current) / granularity)
        reduced = False
        for start in range(0, len(current), chunk_size):
            candidate_events = current[:start] + current[start + chunk_size :]
            candidate = trace.model_copy(update={"events": [*candidate_events, done]})
            attempts += 1
            if await predicate(candidate):
                current = candidate_events
                granularity = max(2, granularity - 1)
                reduced = True
                break
        if reduced:
            continue
        if granularity >= len(current):
            break
        granularity = min(len(current), granularity * 2)
    return trace.model_copy(update={"events": [*current, done]}), attempts


async def reduce_trace(trace: Trace, adapter_name: AdapterName) -> ReductionResult:
    """Reduce a trace while preserving every oracle issue and its observed value."""

    adapter = get_adapter(adapter_name)
    with replay_server(trace) as (server_url, slot):
        initial = evaluate(
            await adapter.observe_url(server_url, trace.trace_id),
            trace.ground_truth,
        )
        signature = tuple(sorted(issue.code for issue in initial.issues))
        fingerprint = tuple(issue.model_dump_json() for issue in initial.issues)
        if not signature:
            raise ValueError("trace does not fail for the selected adapter")

        async def preserves_signature(candidate: Trace) -> bool:
            slot.replace(candidate)
            report = evaluate(
                await adapter.observe_url(server_url, candidate.trace_id),
                candidate.ground_truth,
            )
            return tuple(issue.model_dump_json() for issue in report.issues) == fingerprint

        reduced, attempts = await minimize_events(trace, preserves_signature)

    return ReductionResult(
        adapter=adapter_name,
        failure_signature=list(signature),
        original_event_count=len(trace.events),
        reduced_event_count=len(reduced.events),
        attempts=attempts,
        trace=reduced,
    )
