from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePath
from typing import Protocol

from agent_router.core.models import Agent, AgentRouterError


class PluginActivation(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class ArtifactPolicy(StrEnum):
    INHERIT = "inherit"
    ENABLED = "enabled"
    DISABLED = "disabled"


class ArtifactEffectiveState(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ABSENT = "absent"


@dataclass(frozen=True, slots=True)
class AgentEnvironment:
    root: Path
    project_root: Path | None = None

    def __post_init__(self) -> None:
        root = Path(self.root).resolve()
        project = (
            Path(self.project_root).resolve()
            if self.project_root is not None
            else root
        )
        object.__setattr__(self, "root", root)
        object.__setattr__(self, "project_root", project)


@dataclass(frozen=True, slots=True)
class PluginRef:
    agent: Agent
    native_ref: str
    scope: str = "user"
    source: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "agent", Agent(self.agent))
        if not self.native_ref or not self.scope:
            raise ValueError("plugin native reference and scope must be non-empty")

    def to_dict(self) -> dict[str, object]:
        return {
            "agent": self.agent.value,
            "native_ref": self.native_ref,
            "scope": self.scope,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class PluginRecord:
    ref: PluginRef
    name: str
    installed: bool
    activation: PluginActivation
    installed_version: str | None = None
    available_version: str | None = None
    runtime_root: Path | None = None
    native_evidence: Mapping[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "ref": self.ref.to_dict(),
            "name": self.name,
            "installed": self.installed,
            "activation": self.activation.value,
            "installed_version": self.installed_version,
            "available_version": self.available_version,
            "runtime_root": str(self.runtime_root) if self.runtime_root else None,
            "native_evidence": dict(self.native_evidence or {}),
        }


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    identifier: str
    contract_version: str

    def __post_init__(self) -> None:
        if not self.identifier or not self.contract_version:
            raise ValueError("artifact identifier and contract version must be non-empty")


@dataclass(frozen=True, slots=True)
class PluginArtifactContext:
    plugin: PluginRecord
    root: Path


class ArtifactExtension(Protocol):
    manifest: ArtifactManifest

    def locate(self, context: PluginArtifactContext) -> Iterable[PurePath]: ...


@dataclass(frozen=True, slots=True)
class ArtifactStatus:
    ref: PluginRef
    artifact: ArtifactManifest
    policy: ArtifactPolicy
    effective: ArtifactEffectiveState
    reason: str
    paths: tuple[Path, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "ref": self.ref.to_dict(),
            "artifact": {
                "identifier": self.artifact.identifier,
                "contract_version": self.artifact.contract_version,
            },
            "policy": self.policy.value,
            "effective": self.effective.value,
            "reason": self.reason,
            "paths": [str(path) for path in self.paths],
        }


@dataclass(frozen=True, slots=True)
class PluginLifecycleResult:
    operation: str
    ref: PluginRef
    status: str
    before: PluginRecord | None = None
    after: PluginRecord | None = None

    @property
    def changed(self) -> bool:
        return self.status in {"installed", "updated", "removed"}

    @property
    def verified(self) -> bool:
        return self.status in {"installed", "updated", "removed", "no-op"}

    def to_dict(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "ref": self.ref.to_dict(),
            "status": self.status,
            "changed": self.changed,
            "verified": self.verified,
            "before": self.before.to_dict() if self.before else None,
            "after": self.after.to_dict() if self.after else None,
        }


class PluginError(AgentRouterError):
    pass


class UnsupportedPluginLifecycleError(PluginError):
    pass


class PluginManagerUnavailableError(PluginError):
    pass


class PluginTrustError(PluginError):
    pass


class UnmanagedPluginError(PluginError):
    exit_status = 3


class PluginOperationError(PluginError):
    exit_status = 1
