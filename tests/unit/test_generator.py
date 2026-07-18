from pathlib import Path

from hypothesis import given, settings, strategies as st

from compatflow.generator import DEFAULT_VARIANTS, VariantSpec, decode_trace, generate_variant
from compatflow.replay.store import TraceStore


CORPUS = Path(__file__).parents[2] / "corpus" / "canonical"
GENERATED = Path(__file__).parents[2] / "corpus" / "generated"


def parallel_trace():
    return TraceStore(CORPUS).get("parallel_tool_calls")


def test_canonical_parallel_wire_matches_stored_ground_truth() -> None:
    traces = TraceStore(CORPUS).list()

    assert all(decode_trace(trace) == trace.ground_truth for trace in traces)
    assert [call.index for call in parallel_trace().ground_truth.tool_calls] == [0, 1]


def test_default_variants_are_deterministic_and_semantics_preserving() -> None:
    source = parallel_trace()

    first = [generate_variant(source, spec) for spec in DEFAULT_VARIANTS]
    second = [generate_variant(source, spec) for spec in DEFAULT_VARIANTS]

    assert first == second
    assert len({variant.trace_id for variant in first}) == len(DEFAULT_VARIANTS)
    assert all(decode_trace(variant) == source.ground_truth for variant in first)
    assert {variant.provenance.transformation for variant in first if variant.provenance} == {
        spec.name for spec in DEFAULT_VARIANTS
    }


def test_materialized_corpus_exactly_matches_generator() -> None:
    canonical = TraceStore(CORPUS)
    generated = TraceStore(GENERATED).list()
    specs = {spec.name: spec for spec in DEFAULT_VARIANTS}

    assert len(generated) == 12
    for trace in generated:
        assert trace.provenance is not None
        source = canonical.get(trace.provenance.source_trace_id)
        spec = specs[trace.provenance.transformation]
        assert trace == generate_variant(source, spec)


@settings(max_examples=25, deadline=None)
@given(fragment_size=st.integers(min_value=1, max_value=32))
def test_arbitrary_argument_boundaries_preserve_semantics(fragment_size: int) -> None:
    source = parallel_trace()
    spec = VariantSpec(name=f"size_{fragment_size}", fragment_size=fragment_size)

    variant = generate_variant(source, spec)

    assert decode_trace(variant) == source.ground_truth
