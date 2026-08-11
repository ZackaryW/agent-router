from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re

from agent_router.utils.destinations import Destination

_AGENTS = {"codex", "claude", "kimi", "pi"}
_KINDS = {"skill", "hook"}
_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class RouterStateError(ValueError):
    """Router-owned state scope or location is invalid."""


@dataclass(frozen=True, slots=True)
class StateLocations:
    current: Path
    legacy: Path


def resolve_state_root(
    scope: str,
    *,
    home: Path,
    project_root: Path | None,
) -> Path:
    if scope == "user":
        return Path(home).resolve() / ".z-agent-router"
    if scope == "project" and project_root is not None:
        return Path(project_root).resolve() / ".z-agent-router"
    raise RouterStateError("project router state requires an explicit project root")


def ownership_locations(
    *,
    state_root: Path,
    destination: Destination,
    agent: str,
    kind: str,
    name: str,
) -> StateLocations:
    if agent not in _AGENTS or kind not in _KINDS or not _NAME.fullmatch(name):
        raise RouterStateError("ownership state identity is invalid")
    canonical = str(destination.path.resolve())
    digest = sha256(canonical.encode("utf-8")).hexdigest()
    current = (
        Path(state_root).resolve()
        / "ownership"
        / agent
        / kind
        / digest
        / f"{name}.json"
    )
    legacy_root = (
        destination.path.parent if destination.shared_config else destination.path
    )
    legacy = legacy_root / ".agent-router" / kind / f"{name}.json"
    return StateLocations(current, legacy)
