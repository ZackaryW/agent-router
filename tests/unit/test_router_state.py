from pathlib import Path
from hashlib import sha256

import pytest

from agent_router.utils.router_state import RouterStateError, resolve_state_root
from agent_router.utils.destinations import Destination
from agent_router.utils.router_state import ownership_locations


def test_resolves_state_root_from_semantic_scope(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = tmp_path / "project"

    assert resolve_state_root("user", home=home, project_root=None) == (
        home / ".z-agent-router"
    )
    assert resolve_state_root("project", home=home, project_root=project) == (
        project / ".z-agent-router"
    )


@pytest.mark.parametrize(
    ("scope", "project_root"),
    [("project", None), ("session", Path("project"))],
)
def test_rejects_an_invalid_state_scope(
    tmp_path: Path, scope: str, project_root: Path | None
) -> None:
    selected_project = tmp_path / project_root if project_root is not None else None

    with pytest.raises(RouterStateError):
        resolve_state_root(scope, home=tmp_path / "home", project_root=selected_project)


def test_resolves_collision_safe_current_and_exact_legacy_ownership_paths(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "project" / ".z-agent-router"
    destination = Destination(tmp_path / "project" / ".agents" / "skills", False)
    canonical = str(destination.path.resolve())
    digest = sha256(canonical.encode("utf-8")).hexdigest()

    locations = ownership_locations(
        state_root=state_root,
        destination=destination,
        agent="codex",
        kind="skill",
        name="reviewer",
    )

    assert locations.current == (
        state_root / "ownership" / "codex" / "skill" / digest / "reviewer.json"
    )
    assert locations.legacy == (
        destination.path / ".agent-router" / "skill" / "reviewer.json"
    )


@pytest.mark.parametrize(
    ("agent", "kind", "name"),
    [
        ("unknown", "skill", "reviewer"),
        ("codex", "plugin", "reviewer"),
        ("codex", "skill", "../reviewer"),
    ],
)
def test_rejects_unsafe_ownership_location_identity(
    tmp_path: Path, agent: str, kind: str, name: str
) -> None:
    with pytest.raises(RouterStateError):
        ownership_locations(
            state_root=tmp_path / ".z-agent-router",
            destination=Destination(tmp_path / ".agents" / "skills", False),
            agent=agent,
            kind=kind,
            name=name,
        )
