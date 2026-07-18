"""Deterministic, semantics-preserving trace generation."""

from compatflow.generator.semantics import TraceSemanticError, decode_trace
from compatflow.generator.variants import DEFAULT_VARIANTS, VariantSpec, generate_variant

__all__ = [
    "DEFAULT_VARIANTS",
    "TraceSemanticError",
    "VariantSpec",
    "decode_trace",
    "generate_variant",
]

