from __future__ import annotations

import os
from pathlib import Path

from agent_router.core.models import Agent, UnsupportedScopeError
from agent_router.core.plugins import (
    AgentEnvironment,
    ArtifactEffectiveState,
    ArtifactExtension,
    ArtifactManifest,
    ArtifactPolicy,
    ArtifactStatus,
    PluginActivation,
    PluginArtifactContext,
    PluginLifecycleResult,
    PluginManagerUnavailableError,
    PluginOperationError,
    PluginRecord,
    PluginRef,
    PluginTrustError,
    UnmanagedPluginError,
    UnsupportedPluginLifecycleError,
)
from agent_router.utils.artifact_paths import resolve_artifact_paths
from agent_router.utils.plugin_evidence import (
    NativePluginEvidence,
    decode_claude_plugins,
    decode_codex_plugins,
    decode_kimi_plugins,
    decode_pi_packages,
)
from agent_router.utils.plugin_state import (
    ArtifactPolicyOverride,
    PluginOwnershipReceipt,
    PluginStateKey,
    clear_artifact_policy,
    load_plugin_state,
    plugin_state_path,
    put_receipt,
    remove_receipt,
    save_plugin_state,
    set_artifact_policy,
)
from agent_router.utils.process import (
    ProcessExecutionError,
    ProcessRequest,
    ProcessResult,
    ProcessRunner,
    run_process,
)

_SCOPES = {
    Agent.CODEX: {"user"},
    Agent.CLAUDE: {"user", "project", "local", "managed"},
    Agent.KIMI: {"user"},
    Agent.PI: {"user", "project"},
}


class PluginManager:
    def __init__(
        self,
        agent: Agent,
        environment: AgentEnvironment,
        extensions: tuple[ArtifactExtension, ...] = (),
        runner: ProcessRunner = run_process,
    ) -> None:
        self.agent = agent
        self.environment = environment
        self.runner = runner
        self.extensions: dict[str, ArtifactExtension] = {}
        for extension in extensions:
            identifier = extension.manifest.identifier
            if identifier in self.extensions:
                raise ValueError(f"duplicate artifact extension: {identifier}")
            self.extensions[identifier] = extension

    def discover(self, *, include_available: bool = False) -> tuple[PluginRecord, ...]:
        if self.agent is Agent.KIMI:
            evidence = decode_kimi_plugins(self.environment.root)
        else:
            argv = self._discovery_argv(include_available)
            result = self._run(argv)
            if result.returncode != 0:
                raise PluginOperationError(
                    f"{self.agent.value} plugin discovery failed: {result.stderr.strip()}"
                )
            if self.agent is Agent.CODEX:
                evidence = decode_codex_plugins(result.stdout)
            elif self.agent is Agent.CLAUDE:
                evidence = decode_claude_plugins(result.stdout)
            else:
                evidence = decode_pi_packages(result.stdout)
        records = tuple(self._record(item) for item in evidence)
        return records if include_available else tuple(item for item in records if item.installed)

    def install(self, ref: PluginRef, *, trust: bool = False) -> PluginLifecycleResult:
        self._preflight(ref, "install")
        if self._is_direct(ref) and not trust:
            raise PluginTrustError("direct URL, Git, and local plugin sources require trust")
        before = self._find(self.discover(), ref)
        if before is not None:
            return PluginLifecycleResult("install", ref, "no-op", before, before)
        result = self._run(self._mutation_argv("install", ref))
        if result.returncode != 0:
            raise PluginOperationError(
                f"{self.agent.value} plugin install failed: {result.stderr.strip()}"
            )
        try:
            after = self._find(self.discover(), ref)
        except Exception:
            return PluginLifecycleResult("install", ref, "indeterminate", before, None)
        if after is None:
            return PluginLifecycleResult("install", ref, "indeterminate", before, None)
        state_path = plugin_state_path(self.environment.root)
        state = put_receipt(
            load_plugin_state(state_path),
            PluginOwnershipReceipt(self._key(ref), ref.source),
        )
        save_plugin_state(state_path, state)
        return PluginLifecycleResult("install", after.ref, "installed", before, after)

    def update(self, ref: PluginRef) -> PluginLifecycleResult:
        self._preflight(ref, "update")
        self._require_owned(ref)
        before = self._find(self.discover(), ref)
        if before is None:
            raise PluginOperationError("owned plugin is absent from authoritative state")
        commands = self._update_argv(ref)
        for argv in commands:
            result = self._run(argv)
            if result.returncode != 0:
                raise PluginOperationError(
                    f"{self.agent.value} plugin update failed: {result.stderr.strip()}"
                )
        try:
            after = self._find(self.discover(), ref)
        except Exception:
            return PluginLifecycleResult("update", ref, "partially-changed", before, None)
        if after is None:
            return PluginLifecycleResult("update", ref, "partially-changed", before, None)
        status = (
            "no-op"
            if (before.installed_version, before.runtime_root)
            == (after.installed_version, after.runtime_root)
            else "updated"
        )
        return PluginLifecycleResult("update", after.ref, status, before, after)

    def remove(self, ref: PluginRef) -> PluginLifecycleResult:
        self._preflight(ref, "remove")
        self._require_owned(ref)
        before = self._find(self.discover(), ref)
        if before is None:
            raise PluginOperationError("owned plugin is absent from authoritative state")
        result = self._run(self._mutation_argv("remove", ref))
        if result.returncode != 0:
            raise PluginOperationError(
                f"{self.agent.value} plugin removal failed: {result.stderr.strip()}"
            )
        try:
            after = self._find(self.discover(), ref)
        except Exception:
            return PluginLifecycleResult("remove", ref, "partially-changed", before, None)
        if after is not None:
            return PluginLifecycleResult("remove", ref, "indeterminate", before, after)
        state_path = plugin_state_path(self.environment.root)
        save_plugin_state(
            state_path, remove_receipt(load_plugin_state(state_path), self._key(ref))
        )
        return PluginLifecycleResult("remove", ref, "removed", before, None)

    def resolve_artifacts(self, identifier: str) -> tuple[ArtifactStatus, ...]:
        extension = self._extension(identifier)
        return tuple(
            self._artifact_status(record.ref, extension, record)
            for record in self.discover()
        )

    def artifact_status(self, ref: PluginRef, identifier: str) -> ArtifactStatus:
        extension = self._extension(identifier)
        record = self._find(self.discover(), ref)
        return self._artifact_status(ref, extension, record)

    def set_artifact_policy(
        self, ref: PluginRef, identifier: str, policy: ArtifactPolicy
    ) -> ArtifactStatus:
        selected = ArtifactPolicy(policy)
        state_path = plugin_state_path(self.environment.root)
        state = load_plugin_state(state_path)
        if selected is ArtifactPolicy.INHERIT:
            state = clear_artifact_policy(state, self._key(ref), identifier)
        else:
            state = set_artifact_policy(
                state,
                ArtifactPolicyOverride(self._key(ref), identifier, selected.value),
            )
        save_plugin_state(state_path, state)
        return self.artifact_status(ref, identifier)

    def clear_artifact_policy(self, ref: PluginRef, identifier: str) -> ArtifactStatus:
        return self.set_artifact_policy(ref, identifier, ArtifactPolicy.INHERIT)

    def _artifact_status(
        self,
        ref: PluginRef,
        extension: ArtifactExtension,
        record: PluginRecord | None,
    ) -> ArtifactStatus:
        policy = self._policy(ref, extension.manifest.identifier)
        if record is None or not record.installed:
            return ArtifactStatus(
                ref,
                extension.manifest,
                policy,
                ArtifactEffectiveState.ABSENT,
                "plugin-absent",
            )
        if record.activation is PluginActivation.DISABLED:
            return ArtifactStatus(
                record.ref,
                extension.manifest,
                policy,
                ArtifactEffectiveState.INACTIVE,
                "native-disabled",
            )
        if policy is ArtifactPolicy.DISABLED:
            return ArtifactStatus(
                record.ref,
                extension.manifest,
                policy,
                ArtifactEffectiveState.INACTIVE,
                "router-disabled",
            )
        eligible = record.activation is PluginActivation.ENABLED or (
            record.ref.agent is Agent.PI
            and record.activation in {PluginActivation.PARTIAL, PluginActivation.UNKNOWN}
        )
        if not eligible or record.runtime_root is None:
            reason = "runtime-root-unverified" if record.runtime_root is None else "native-unknown"
            return ArtifactStatus(
                record.ref,
                extension.manifest,
                policy,
                ArtifactEffectiveState.INACTIVE,
                reason,
            )
        context = PluginArtifactContext(record, record.runtime_root)
        paths = resolve_artifact_paths(record.runtime_root, extension.locate(context))
        return ArtifactStatus(
            record.ref,
            extension.manifest,
            policy,
            ArtifactEffectiveState.ACTIVE if paths else ArtifactEffectiveState.ABSENT,
            "eligible" if paths else "artifact-absent",
            paths,
        )

    def _policy(self, ref: PluginRef, identifier: str) -> ArtifactPolicy:
        state = load_plugin_state(plugin_state_path(self.environment.root))
        for override in state.overrides:
            if override.key == self._key(ref) and override.artifact_id == identifier:
                return ArtifactPolicy(override.policy)
        return ArtifactPolicy.INHERIT

    def _extension(self, identifier: str) -> ArtifactExtension:
        try:
            return self.extensions[identifier]
        except KeyError as error:
            raise PluginOperationError(f"artifact extension is not registered: {identifier}") from error

    def _record(self, item: NativePluginEvidence) -> PluginRecord:
        root = item.runtime_root
        if root is not None:
            try:
                root = root.resolve(strict=True)
                if not root.is_absolute() or not root.is_dir():
                    root = None
            except OSError:
                root = None
        try:
            activation = PluginActivation(item.activation)
        except ValueError:
            activation = PluginActivation.UNKNOWN
        return PluginRecord(
            PluginRef(self.agent, item.native_ref, item.scope, item.source),
            item.name,
            item.installed,
            activation,
            item.installed_version,
            item.available_version,
            root,
            item.details,
        )

    def _find(
        self, records: tuple[PluginRecord, ...], ref: PluginRef
    ) -> PluginRecord | None:
        for record in records:
            if (
                record.ref.agent is ref.agent
                and record.ref.native_ref == ref.native_ref
                and record.ref.scope == ref.scope
                and (ref.source is None or record.ref.source == ref.source)
            ):
                return record
        return None

    def _preflight(self, ref: PluginRef, operation: str) -> None:
        if ref.agent is not self.agent:
            raise PluginOperationError("plugin reference belongs to a different agent")
        if self.agent is Agent.KIMI:
            raise UnsupportedPluginLifecycleError(
                "Kimi plugin lifecycle has no supported noninteractive manager"
            )
        if ref.scope not in _SCOPES[self.agent]:
            raise UnsupportedScopeError(
                f"{self.agent.value} does not support plugin scope {ref.scope!r}"
            )
        if self.agent is Agent.CLAUDE and ref.scope == "managed" and operation != "update":
            raise UnsupportedScopeError("Claude managed plugins support update only")

    def _require_owned(self, ref: PluginRef) -> None:
        state = load_plugin_state(plugin_state_path(self.environment.root))
        if not any(receipt.key == self._key(ref) for receipt in state.receipts):
            raise UnmanagedPluginError(
                f"plugin was not installed by agent-router: {ref.native_ref} ({ref.scope})"
            )

    def _key(self, ref: PluginRef) -> PluginStateKey:
        return PluginStateKey(ref.agent.value, ref.scope, ref.native_ref)

    def _is_direct(self, ref: PluginRef) -> bool:
        value = ref.native_ref
        return (
            value.startswith(
                (
                    "http://",
                    "https://",
                    "git:",
                    "git@",
                    "ssh://",
                    "file://",
                    "./",
                    "../",
                    ".\\",
                    "..\\",
                    "~/",
                    "~\\",
                )
            )
            or Path(value).is_absolute()
            or value.endswith(".git")
        )

    def _discovery_argv(self, include_available: bool) -> tuple[str, ...]:
        if self.agent is Agent.CODEX:
            return ("codex", "plugin", "list", *(('--available',) if include_available else ()), "--json")
        if self.agent is Agent.CLAUDE:
            return ("claude", "plugin", "list", *(('--available',) if include_available else ()), "--json")
        return ("pi", "list", "--no-approve")

    def _mutation_argv(self, operation: str, ref: PluginRef) -> tuple[str, ...]:
        if self.agent is Agent.CODEX:
            command = "add" if operation == "install" else "remove"
            return ("codex", "plugin", command, ref.native_ref, "--json")
        if self.agent is Agent.CLAUDE:
            command = "install" if operation == "install" else "uninstall"
            argv = ["claude", "plugin", command, ref.native_ref, "--scope", ref.scope]
            if operation == "remove":
                argv.append("--yes")
            return tuple(argv)
        command = "install" if operation == "install" else "remove"
        argv = ["pi", command, ref.native_ref]
        if ref.scope == "project":
            argv.append("--local")
        argv.append("--no-approve")
        return tuple(argv)

    def _update_argv(self, ref: PluginRef) -> tuple[tuple[str, ...], ...]:
        if self.agent is Agent.CODEX:
            marketplace = ref.source or (ref.native_ref.rsplit("@", 1)[1] if "@" in ref.native_ref else None)
            if not marketplace:
                raise PluginOperationError("Codex update requires an owning marketplace")
            return (
                ("codex", "plugin", "marketplace", "upgrade", marketplace, "--json"),
                ("codex", "plugin", "add", ref.native_ref, "--json"),
            )
        if self.agent is Agent.CLAUDE:
            return (("claude", "plugin", "update", ref.native_ref, "--scope", ref.scope),)
        return (("pi", "update", ref.native_ref, "--no-approve"),)

    def _run(self, argv: tuple[str, ...]) -> ProcessResult:
        environment = dict(os.environ)
        variable = {
            Agent.CODEX: "CODEX_HOME",
            Agent.CLAUDE: "CLAUDE_CONFIG_DIR",
            Agent.PI: "PI_CODING_AGENT_DIR",
        }[self.agent]
        environment[variable] = str(self.environment.root)
        try:
            return self.runner(
                ProcessRequest(
                    argv,
                    cwd=self.environment.project_root,
                    environment=environment,
                    timeout=60,
                )
            )
        except ProcessExecutionError as error:
            raise PluginManagerUnavailableError(
                f"{self.agent.value} plugin manager is unavailable"
            ) from error
