"""Command-line entry point for the replay server."""

from __future__ import annotations

import os

import uvicorn

from compatflow.replay.app import create_app


def main() -> None:
    """Run the server using environment-based host and port overrides."""

    uvicorn.run(
        create_app(),
        host=os.getenv("COMPATFLOW_HOST", "127.0.0.1"),
        port=int(os.getenv("COMPATFLOW_PORT", "8000")),
    )


if __name__ == "__main__":
    main()

