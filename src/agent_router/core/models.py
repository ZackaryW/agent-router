from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Agent(StrEnum):
    CODEX = "codex"
    CLAUDE = "claude"
    KIMI = "kimi"
    PI = "pi"


class Scope(StrEnum):
    USER = "user"
    PROJECT = "project"


class AssetKind(StrEnum):
    SKILL = "skill"
    HOOK = "hook"


class HookTransition(StrEnum):
    LEGACY_REPLACED = "legacy-replaced"
    LEGACY_PRUNED = "legacy-pruned"
    OWNED_RESTORED = "owned-restored"
    OWNED_REMOVED = "owned-removed"


class AgentRouterError(Exception):
    exit_status = 2


class InvalidAssetError(AgentRouterError):
    pass


class UnsupportedAssetError(AgentRouterError):
    pass


class UnsupportedScopeError(AgentRouterError):
    pass


class ConflictError(AgentRouterError):
    exit_status = 3


@dataclass(frozen=True, slots=True)
class LifecycleResult:
    operation: str
    kind: AssetKind
    name: str
    agent: Agent
    scope: Scope
    destination: Path
    status: str
    compatible_agents: tuple[Agent, ...] = ()
    converted: bool = False
    hook_transition: HookTransition | None = None

    @property
    def changed(self) -> bool:
        return self.status in {"installed", "updated", "removed"}

    def to_dict(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "kind": self.kind.value,
            "name": self.name,
            "agent": self.agent.value,
            "scope": self.scope.value,
            "destination": str(self.destination),
            "status": self.status,
            "changed": self.changed,
            "compatible_agents": [agent.value for agent in self.compatible_agents],
            "converted": self.converted,
            "hook_transition": (
                self.hook_transition.value if self.hook_transition is not None else None
            ),
        }
