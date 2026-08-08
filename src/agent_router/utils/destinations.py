from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class UnsupportedDestinationError(ValueError):
    """An agent has no native surface for the requested destination."""


@dataclass(frozen=True, slots=True)
class Destination:
    path: Path
    shared_config: bool


_DESTINATIONS: dict[tuple[str, str, str], tuple[str, bool]] = {
    ("codex", "skill", "user"): (".codex/skills", False),
    ("codex", "skill", "project"): (".agents/skills", False),
    ("claude", "skill", "user"): (".claude/skills", False),
    ("claude", "skill", "project"): (".claude/skills", False),
    ("kimi", "skill", "user"): (".kimi-code/skills", False),
    ("kimi", "skill", "project"): (".kimi-code/skills", False),
    ("pi", "skill", "user"): (".pi/agent/skills", False),
    ("pi", "skill", "project"): (".pi/skills", False),
    ("codex", "hook", "user"): (".codex/hooks.json", True),
    ("codex", "hook", "project"): (".codex/hooks.json", True),
    ("claude", "hook", "user"): (".claude/settings.json", True),
    ("claude", "hook", "project"): (".claude/settings.json", True),
    ("kimi", "hook", "user"): (".kimi-code/config.toml", True),
    ("pi", "hook", "user"): (".pi/agent/extensions", False),
    ("pi", "hook", "project"): (".pi/extensions", False),
}


def resolve_destination(
    agent: str,
    kind: str,
    scope: str,
    *,
    home: Path,
    project_root: Path | None,
) -> Destination:
    if scope == "project" and project_root is None:
        raise UnsupportedDestinationError("project scope requires a project root")
    try:
        relative, shared = _DESTINATIONS[(agent, kind, scope)]
    except KeyError as error:
        raise UnsupportedDestinationError(
            f"{agent} does not support {scope} {kind} destinations"
        ) from error
    base = project_root if scope == "project" else home
    assert base is not None
    return Destination(base.joinpath(*relative.split("/")), shared)
