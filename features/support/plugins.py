from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path, PurePath

from agent_router import (
    Agent,
    AgentEnvironment,
    AgentRouter,
    ArtifactManifest,
    PluginArtifactContext,
    PluginRef,
)
from agent_router.utils.process import (
    ProcessExecutionError,
    ProcessRequest,
    ProcessResult,
)


@dataclass
class FakePlugin:
    native_ref: str
    scope: str = "user"
    source: str | None = "configured"
    version: str = "1.0"
    enabled: bool = True
    root: Path | None = None


@dataclass
class FakeNativeManager:
    root: Path
    installed: list[FakePlugin] = field(default_factory=list)
    available: list[FakePlugin] = field(default_factory=list)
    calls: list[ProcessRequest] = field(default_factory=list)
    successful_without_change: bool = False
    fail_discovery_after_mutation: bool = False
    unavailable: bool = False
    mutation_seen: bool = False

    def add(
        self,
        native_ref: str = "review@configured",
        *,
        scope: str = "user",
        source: str | None = "configured",
        enabled: bool = True,
        version: str = "1.0",
    ) -> FakePlugin:
        path = self.root / "runtime" / scope / _safe(native_ref) / version
        path.mkdir(parents=True, exist_ok=True)
        plugin = FakePlugin(native_ref, scope, source, version, enabled, path)
        self.installed.append(plugin)
        return plugin

    def __call__(self, request: ProcessRequest) -> ProcessResult:
        self.calls.append(request)
        if self.unavailable:
            raise ProcessExecutionError("process could not start", request)
        argv = request.argv
        if "list" in argv:
            if self.fail_discovery_after_mutation and self.mutation_seen:
                return ProcessResult(1, "", "rediscovery failed")
            return ProcessResult(0, self._inventory(argv[0], "--available" in argv), "")
        if "upgrade" in argv:
            self.mutation_seen = True
            return ProcessResult(0, "{}", "")
        self.mutation_seen = True
        if not self.successful_without_change:
            self._mutate(argv)
        return ProcessResult(0, "{}", "")

    def _mutate(self, argv: tuple[str, ...]) -> None:
        executable = argv[0]
        if executable == "codex":
            operation, native_ref = argv[2], argv[3]
            scope = "user"
        elif executable == "claude":
            operation, native_ref = argv[2], argv[3]
            scope = argv[argv.index("--scope") + 1]
        else:
            operation, native_ref = argv[1], argv[2]
            scope = "project" if "--local" in argv else "user"
        match = next(
            (
                item
                for item in self.installed
                if item.native_ref == native_ref and item.scope == scope
            ),
            None,
        )
        if operation in {"add", "install"}:
            if match is None:
                source = native_ref.rsplit("@", 1)[-1] if "@" in native_ref else None
                self.add(native_ref, scope=scope, source=source)
            elif executable == "codex" and operation == "add":
                self._move(match)
        elif operation == "update":
            if match is not None:
                self._move(match)
        elif operation in {"remove", "uninstall"} and match is not None:
            self.installed.remove(match)

    def _move(self, plugin: FakePlugin) -> None:
        plugin.version = str(float(plugin.version) + 1)
        plugin.root = self.root / "runtime" / plugin.scope / _safe(plugin.native_ref) / plugin.version
        plugin.root.mkdir(parents=True, exist_ok=True)

    def _inventory(self, executable: str, include_available: bool) -> str:
        if executable == "codex":
            return json.dumps(
                {
                    "installed": [self._codex(item, True) for item in self.installed],
                    "available": [self._codex(item, False) for item in self.available]
                    if include_available
                    else [],
                }
            )
        if executable == "claude":
            installed = [self._claude_installed(item) for item in self.installed]
            if include_available:
                return json.dumps(
                    {
                        "installed": installed,
                        "available": [self._claude_available(item) for item in self.available],
                    }
                )
            return json.dumps(installed)
        lines: list[str] = []
        for heading, scope in (("User packages:", "user"), ("Project packages:", "project")):
            scoped = [item for item in self.installed if item.scope == scope]
            lines.append(heading)
            for item in scoped:
                lines.extend((f"  {item.native_ref}", f"    {item.root}"))
        return "\n".join(lines) + ("\n" if lines else "")

    def _codex(self, item: FakePlugin, installed: bool) -> dict[str, object]:
        name, marketplace = _split(item.native_ref)
        return {
            "pluginId": item.native_ref,
            "name": name,
            "marketplaceName": item.source or marketplace or "configured",
            "version": item.version,
            "installed": installed,
            "enabled": item.enabled if installed else False,
            "source": {"source": "local", "path": str(item.root)}
            if installed
            else {"source": "git", "url": "https://example.test/plugin"},
        }

    def _claude_installed(self, item: FakePlugin) -> dict[str, object]:
        return {
            "id": item.native_ref,
            "version": item.version,
            "scope": item.scope,
            "enabled": item.enabled,
            "installPath": str(item.root),
            "installedAt": "2026-08-08T00:00:00Z",
        }

    def _claude_available(self, item: FakePlugin) -> dict[str, object]:
        name, marketplace = _split(item.native_ref)
        return {
            "pluginId": item.native_ref,
            "name": name,
            "marketplaceName": item.source or marketplace or "configured",
            "version": item.version,
            "source": "./plugin",
        }


@dataclass(frozen=True, slots=True)
class PathArtifactExtension:
    manifest: ArtifactManifest
    relative_path: PurePath
    contexts: list[PluginArtifactContext] = field(
        default_factory=list, compare=False, hash=False
    )

    def locate(self, context: PluginArtifactContext) -> tuple[PurePath, ...]:
        self.contexts.append(context)
        return (self.relative_path,)


def plugin_router(
    context,
    agent: Agent,
    *,
    extensions=(),
) -> AgentRouter:
    context.native = getattr(context, "native", FakeNativeManager(context.destination))
    context.environment = AgentEnvironment(
        context.destination, getattr(context, "project_root", None)
    )
    return AgentRouter(
        agent,
        environment=context.environment,
        extensions=tuple(extensions),
        process_runner=context.native,
    )


def ref(agent: Agent, native_ref: str = "review@configured", scope: str = "user") -> PluginRef:
    source = native_ref.rsplit("@", 1)[1] if "@" in native_ref else None
    return PluginRef(agent, native_ref, scope, source)


def _split(native_ref: str) -> tuple[str, str | None]:
    if "@" not in native_ref:
        return native_ref, None
    return tuple(native_ref.rsplit("@", 1))  # type: ignore[return-value]


def _safe(value: str) -> str:
    return value.replace(":", "_").replace("/", "_").replace("@", "_")
