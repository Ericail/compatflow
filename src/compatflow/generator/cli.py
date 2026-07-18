"""CLI for materializing deterministic trace variants."""

from __future__ import annotations

import argparse
from pathlib import Path

from compatflow.generator.variants import DEFAULT_VARIANTS, generate_variant
from compatflow.replay.models import Trace


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate semantics-preserving CompatFlow traces")
    parser.add_argument("source", type=Path, help="canonical trace JSON file")
    parser.add_argument("output", type=Path, help="directory for generated variants")
    args = parser.parse_args()

    source = Trace.model_validate_json(args.source.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    for spec in DEFAULT_VARIANTS:
        variant = generate_variant(source, spec)
        output_path = args.output / f"{variant.trace_id}.json"
        output_path.write_text(
            variant.model_dump_json(indent=2, exclude_none=True) + "\n",
            encoding="utf-8",
        )
        print(output_path)


if __name__ == "__main__":
    main()
