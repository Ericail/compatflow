"""CLI for running an adapter-by-trace compatibility matrix."""

from __future__ import annotations

import argparse
import asyncio
from typing import cast

from compatflow.adapters import ADAPTER_NAMES, AdapterName
from compatflow.matrix import run_matrix


async def _run(server_url: str, adapter_names: tuple[AdapterName, ...]) -> int:
    report = await run_matrix(server_url, adapter_names)
    print(report.model_dump_json(indent=2))
    return 0 if report.failed == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CompatFlow client-by-trace matrix")
    parser.add_argument("--server", default="http://127.0.0.1:8000", help="replay server URL")
    parser.add_argument(
        "--adapter",
        action="append",
        choices=ADAPTER_NAMES,
        help="adapter to include; repeat this flag, or omit it to run all adapters",
    )
    args = parser.parse_args()
    selected = tuple(args.adapter or ADAPTER_NAMES)
    adapter_names = cast(tuple[AdapterName, ...], selected)
    raise SystemExit(asyncio.run(_run(args.server, adapter_names)))


if __name__ == "__main__":
    main()

