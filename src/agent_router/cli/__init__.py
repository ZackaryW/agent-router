from __future__ import annotations

import sys


def main() -> int | None:
    try:
        from agent_router.cli.app import app
    except ModuleNotFoundError as error:
        if error.name != "typer":
            raise
        print(
            "agent-router CLI is optional; install 'agent_router[cli]' to use it.",
            file=sys.stderr,
        )
        return 2
    app()
    return None


__all__ = ["main"]
