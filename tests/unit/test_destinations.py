from pathlib import Path

import pytest

from agent_router.utils.destinations import (
    UnsupportedDestinationError,
    resolve_destination,
)


@pytest.mark.parametrize(
    ("agent", "kind", "scope", "relative", "shared"),
    [
        ("codex", "skill", "user", ".codex/skills", False),
        ("codex", "skill", "project", ".agents/skills", False),
        ("claude", "skill", "user", ".claude/skills", False),
        ("claude", "skill", "project", ".claude/skills", False),
        ("kimi", "skill", "user", ".kimi-code/skills", False),
        ("kimi", "skill", "project", ".kimi-code/skills", False),
        ("pi", "skill", "user", ".pi/agent/skills", False),
        ("pi", "skill", "project", ".pi/skills", False),
        ("codex", "hook", "user", ".codex/hooks.json", True),
        ("codex", "hook", "project", ".codex/hooks.json", True),
        ("claude", "hook", "user", ".claude/settings.json", True),
        ("claude", "hook", "project", ".claude/settings.json", True),
        ("kimi", "hook", "user", ".kimi-code/config.toml", True),
        ("pi", "hook", "user", ".pi/agent/extensions", False),
        ("pi", "hook", "project", ".pi/extensions", False),
    ],
)
def test_resolves_the_native_destination_matrix(
    tmp_path: Path,
    agent: str,
    kind: str,
    scope: str,
    relative: str,
    shared: bool,
) -> None:
    home = tmp_path / "home"
    project = tmp_path / "project"

    destination = resolve_destination(
        agent, kind, scope, home=home, project_root=project if scope == "project" else None
    )

    base = project if scope == "project" else home
    assert destination.path == base.joinpath(*relative.split("/"))
    assert destination.shared_config is shared


def test_project_scope_requires_a_project_root(tmp_path: Path) -> None:
    with pytest.raises(UnsupportedDestinationError, match="project root"):
        resolve_destination("codex", "skill", "project", home=tmp_path, project_root=None)


def test_kimi_project_hooks_are_unsupported(tmp_path: Path) -> None:
    with pytest.raises(UnsupportedDestinationError, match="does not support"):
        resolve_destination(
            "kimi",
            "hook",
            "project",
            home=tmp_path / "home",
            project_root=tmp_path / "project",
        )
