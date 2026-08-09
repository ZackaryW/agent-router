from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

from agent_router.core.assets import Hook, Skill, fragment_fingerprint
from agent_router.core.models import (
    Agent,
    AssetKind,
    ConflictError,
    LifecycleResult,
    Scope,
    UnsupportedAssetError,
    UnsupportedScopeError,
)
from agent_router.core.plugin_manager import PluginManager
from agent_router.core.plugins import (
    AgentEnvironment,
    ArtifactExtension,
    ArtifactPolicy,
    ArtifactStatus,
    PluginLifecycleResult,
    PluginRecord,
    PluginRef,
)
from agent_router.utils.assets import (
    AssetError,
    AssetFile,
    collect_asset_tree,
    fingerprint_asset,
)
from agent_router.utils.destinations import (
    Destination,
    UnsupportedDestinationError,
    resolve_destination,
)
from agent_router.utils.mutation import MutationPlan, Write, apply_mutation
from agent_router.utils.native_hooks import (
    HookDocumentError,
    convert_portable_command_hooks,
    load_json_object,
    reconcile_json_hooks,
    reconcile_kimi_hooks,
    remove_json_hooks,
    remove_kimi_hooks,
    serialize_json,
    serialize_toml,
)
from agent_router.utils.ownership import (
    OwnershipError,
    OwnershipRecord,
    classify_ownership,
    load_ownership,
    ownership_path,
    serialize_ownership,
)
from agent_router.utils.process import ProcessRunner, run_process


class AgentRouter:
    def __init__(
        self,
        agent: Agent,
        *,
        home: str | Path | None = None,
        environment: AgentEnvironment | None = None,
        extensions: tuple[ArtifactExtension, ...] = (),
        process_runner: ProcessRunner = run_process,
    ) -> None:
        self.agent = Agent(agent)
        self.home = Path(home).resolve() if home is not None else Path.home().resolve()
        self.environment = environment or AgentEnvironment(self.home, Path.cwd())
        self._plugins = PluginManager(
            self.agent, self.environment, extensions, process_runner
        )

    def discover_plugins(
        self, *, include_available: bool = False
    ) -> tuple[PluginRecord, ...]:
        return self._plugins.discover(include_available=include_available)

    def install_plugin(
        self, ref: PluginRef, *, trust: bool = False
    ) -> PluginLifecycleResult:
        return self._plugins.install(ref, trust=trust)

    def update_plugin(self, ref: PluginRef) -> PluginLifecycleResult:
        return self._plugins.update(ref)

    def remove_plugin(self, ref: PluginRef) -> PluginLifecycleResult:
        return self._plugins.remove(ref)

    def resolve_artifacts(self, identifier: str) -> tuple[ArtifactStatus, ...]:
        return self._plugins.resolve_artifacts(identifier)

    def artifact_status(self, ref: PluginRef, identifier: str) -> ArtifactStatus:
        return self._plugins.artifact_status(ref, identifier)

    def set_artifact_policy(
        self, ref: PluginRef, identifier: str, policy: ArtifactPolicy
    ) -> ArtifactStatus:
        return self._plugins.set_artifact_policy(ref, identifier, policy)

    def clear_artifact_policy(
        self, ref: PluginRef, identifier: str
    ) -> ArtifactStatus:
        return self._plugins.clear_artifact_policy(ref, identifier)

    def inspect_skill(
        self,
        skill: Skill,
        *,
        scope: Scope = Scope.USER,
        project_root: str | Path | None = None,
        destination: str | Path | None = None,
    ) -> LifecycleResult:
        selected_scope = Scope(scope)
        resolved = self._destination(
            AssetKind.SKILL, selected_scope, project_root, destination
        )
        target = resolved.path / skill.name
        state, _ = self._inspect_dedicated(
            resolved, AssetKind.SKILL, skill.name, target, skill.fingerprint
        )
        if self.agent not in skill.compatible_agents:
            state = "unsupported"
        return self._result(
            "inspect",
            AssetKind.SKILL,
            skill.name,
            selected_scope,
            resolved,
            state,
            skill.compatible_agents,
        )

    def install_skill(
        self,
        skill: Skill,
        *,
        scope: Scope = Scope.USER,
        project_root: str | Path | None = None,
        destination: str | Path | None = None,
        allow_conversion: bool = False,
    ) -> LifecycleResult:
        del allow_conversion
        if self.agent not in skill.compatible_agents:
            raise UnsupportedAssetError(
                f"skill {skill.name!r} is not natively compatible with {self.agent.value}; "
                "skill conversion is not supported"
            )
        selected_scope = Scope(scope)
        resolved = self._destination(
            AssetKind.SKILL, selected_scope, project_root, destination
        )
        target = resolved.path / skill.name
        state, manifest = self._inspect_dedicated(
            resolved, AssetKind.SKILL, skill.name, target, skill.fingerprint
        )
        if state in {"unmanaged", "conflict"}:
            raise ConflictError(f"conflicting skill destination: {target}")
        if state == "current":
            return self._result(
                "install",
                AssetKind.SKILL,
                skill.name,
                selected_scope,
                resolved,
                "no-op",
                skill.compatible_agents,
            )

        record = OwnershipRecord(
            self.agent.value,
            AssetKind.SKILL.value,
            skill.name,
            str(resolved.path.resolve()),
            skill.fingerprint,
            {"target_name": skill.name, "target_type": "directory"},
        )
        writes = tuple(
            Write(target.joinpath(*item.relative_path.split("/")), item.content)
            for item in skill.files
        ) + (Write(manifest, serialize_ownership(record)),)
        replacements = (target,) if state == "outdated" else ()
        apply_mutation(MutationPlan(writes, replacements))
        return self._result(
            "install",
            AssetKind.SKILL,
            skill.name,
            selected_scope,
            resolved,
            "updated" if state == "outdated" else "installed",
            skill.compatible_agents,
        )

    def uninstall_skill(
        self,
        name: str,
        *,
        scope: Scope = Scope.USER,
        project_root: str | Path | None = None,
        destination: str | Path | None = None,
    ) -> LifecycleResult:
        selected_scope = Scope(scope)
        resolved = self._destination(
            AssetKind.SKILL, selected_scope, project_root, destination
        )
        manifest = ownership_path(resolved, AssetKind.SKILL.value, name)
        record = self._require_record(manifest, AssetKind.SKILL, name, resolved)
        target = resolved.path / name
        state, _ = self._inspect_dedicated(
            resolved, AssetKind.SKILL, name, target, record.fingerprint
        )
        if state != "current":
            raise ConflictError(
                f"skill is not an intact agent-router installation: {target}"
            )
        apply_mutation(MutationPlan((), (target, manifest)))
        return self._result(
            "uninstall", AssetKind.SKILL, name, selected_scope, resolved, "removed"
        )

    def inspect_hook(
        self,
        hook: Hook,
        *,
        scope: Scope = Scope.USER,
        project_root: str | Path | None = None,
        destination: str | Path | None = None,
        allow_conversion: bool = False,
    ) -> LifecycleResult:
        selected_scope = Scope(scope)
        resolved = self._destination(
            AssetKind.HOOK, selected_scope, project_root, destination
        )
        try:
            fragment, converted = self._hook_fragment(hook, allow_conversion)
        except UnsupportedAssetError:
            return self._result(
                "inspect",
                AssetKind.HOOK,
                hook.name,
                selected_scope,
                resolved,
                "unsupported",
                hook.compatible_agents,
            )
        if resolved.shared_config:
            state, _ = self._inspect_shared(resolved, hook.name, fragment)
        else:
            target, expected, _ = self._hook_projection(resolved, hook)
            state, _ = self._inspect_dedicated(
                resolved, AssetKind.HOOK, hook.name, target, expected
            )
        return self._result(
            "inspect",
            AssetKind.HOOK,
            hook.name,
            selected_scope,
            resolved,
            state,
            hook.compatible_agents,
            converted,
        )

    def install_hook(
        self,
        hook: Hook,
        *,
        scope: Scope = Scope.USER,
        project_root: str | Path | None = None,
        destination: str | Path | None = None,
        allow_conversion: bool = False,
    ) -> LifecycleResult:
        selected_scope = Scope(scope)
        resolved = self._destination(
            AssetKind.HOOK, selected_scope, project_root, destination
        )
        fragment, converted = self._hook_fragment(hook, allow_conversion)
        if resolved.shared_config:
            state = self._install_shared(resolved, hook.name, fragment)
        else:
            state = self._install_hook_projection(resolved, hook)
        return self._result(
            "install",
            AssetKind.HOOK,
            hook.name,
            selected_scope,
            resolved,
            state,
            hook.compatible_agents,
            converted,
        )

    def uninstall_hook(
        self,
        name: str,
        *,
        scope: Scope = Scope.USER,
        project_root: str | Path | None = None,
        destination: str | Path | None = None,
    ) -> LifecycleResult:
        selected_scope = Scope(scope)
        resolved = self._destination(
            AssetKind.HOOK, selected_scope, project_root, destination
        )
        manifest = ownership_path(resolved, AssetKind.HOOK.value, name)
        record = self._require_record(manifest, AssetKind.HOOK, name, resolved)
        if resolved.shared_config:
            self._uninstall_shared(resolved, record, manifest)
        else:
            details = cast(dict[str, object], record.fragment)
            target = resolved.path / str(details["target_name"])
            state, _ = self._inspect_dedicated(
                resolved,
                AssetKind.HOOK,
                name,
                target,
                record.fingerprint,
                fingerprint_name=cast(str | None, details.get("fingerprint_name")),
            )
            if state != "current":
                raise ConflictError(
                    f"hook is not an intact agent-router installation: {target}"
                )
            apply_mutation(MutationPlan((), (target, manifest)))
        return self._result(
            "uninstall", AssetKind.HOOK, name, selected_scope, resolved, "removed"
        )

    def _destination(
        self,
        kind: AssetKind,
        scope: Scope,
        project_root: str | Path | None,
        override: str | Path | None,
    ) -> Destination:
        root = Path(project_root).resolve() if project_root is not None else None
        try:
            native = resolve_destination(
                self.agent.value,
                kind.value,
                scope.value,
                home=self.home,
                project_root=root,
            )
        except UnsupportedDestinationError as error:
            raise UnsupportedScopeError(str(error)) from error
        return (
            replace(native, path=Path(override).resolve())
            if override is not None
            else native
        )

    def _inspect_dedicated(
        self,
        destination: Destination,
        kind: AssetKind,
        name: str,
        target: Path,
        expected_fingerprint: str,
        *,
        fingerprint_name: str | None = None,
    ) -> tuple[str, Path]:
        manifest = ownership_path(destination, kind.value, name)
        try:
            record = load_ownership(manifest)
            present = target.exists() or target.is_symlink()
            actual = (
                _fingerprint_path(target, fingerprint_name=fingerprint_name)
                if present
                else None
            )
            state = classify_ownership(
                record,
                agent=self.agent.value,
                kind=kind.value,
                name=name,
                destination=destination.path,
                content_present=present,
                actual_fingerprint=actual,
                expected_fingerprint=expected_fingerprint,
            )
        except (AssetError, OwnershipError, OSError, ValueError):
            state = "conflict"
        return state, manifest

    def _hook_fragment(self, hook: Hook, allow_conversion: bool) -> tuple[object, bool]:
        if self.agent in hook.compatible_agents:
            return hook.fragment, False
        if (
            allow_conversion
            and hook.format == "json"
            and self.agent in {Agent.CLAUDE, Agent.CODEX}
        ):
            try:
                converted = convert_portable_command_hooks(
                    {"hooks": hook.fragment}, self.agent.value
                )
            except HookDocumentError as error:
                raise UnsupportedAssetError(str(error)) from error
            return converted["hooks"], True
        raise UnsupportedAssetError(
            f"hook {hook.name!r} is not compatible with {self.agent.value}"
        )

    def _hook_projection(
        self, destination: Destination, hook: Hook
    ) -> tuple[Path, str, str | None]:
        if hook.format == "pi-file":
            source_name = hook.files[0].relative_path
            return destination.path / source_name, hook.fingerprint, source_name
        if hook.format == "pi-directory":
            return destination.path / hook.name, hook.fingerprint, None
        raise UnsupportedAssetError(
            f"{self.agent.value} requires a native extension artifact"
        )

    def _install_hook_projection(self, destination: Destination, hook: Hook) -> str:
        target, expected, fingerprint_name = self._hook_projection(destination, hook)
        state, manifest = self._inspect_dedicated(
            destination,
            AssetKind.HOOK,
            hook.name,
            target,
            expected,
            fingerprint_name=fingerprint_name,
        )
        if state in {"unmanaged", "conflict"}:
            raise ConflictError(f"conflicting hook destination: {target}")
        if state == "current":
            return "no-op"
        if hook.format == "pi-file":
            writes = (Write(target, hook.files[0].content),)
            target_type = "file"
        else:
            writes = tuple(
                Write(target.joinpath(*item.relative_path.split("/")), item.content)
                for item in hook.files
            )
            target_type = "directory"
        record = OwnershipRecord(
            self.agent.value,
            AssetKind.HOOK.value,
            hook.name,
            str(destination.path.resolve()),
            expected,
            {
                "target_name": target.name,
                "target_type": target_type,
                "fingerprint_name": fingerprint_name,
            },
        )
        writes += (Write(manifest, serialize_ownership(record)),)
        apply_mutation(MutationPlan(writes, (target,) if state == "outdated" else ()))
        return "updated" if state == "outdated" else "installed"

    def _inspect_shared(
        self, destination: Destination, name: str, expected_fragment: object
    ) -> tuple[str, Path]:
        manifest = ownership_path(destination, AssetKind.HOOK.value, name)
        try:
            record = load_ownership(manifest)
            probe = record.fragment if record is not None else expected_fragment
            present = self._shared_fragment_present(destination, probe)
            actual = fragment_fingerprint(probe) if present else None
            state = classify_ownership(
                record,
                agent=self.agent.value,
                kind=AssetKind.HOOK.value,
                name=name,
                destination=destination.path,
                content_present=present,
                actual_fingerprint=actual,
                expected_fingerprint=fragment_fingerprint(expected_fragment),
            )
        except (OwnershipError, HookDocumentError, OSError, ValueError, TypeError):
            state = "conflict"
        return state, manifest

    def _install_shared(
        self, destination: Destination, name: str, fragment: object
    ) -> str:
        state, manifest = self._inspect_shared(destination, name, fragment)
        if state in {"unmanaged", "conflict"}:
            raise ConflictError(f"conflicting hook destination: {destination.path}")
        if state == "current":
            return "no-op"
        prior = load_ownership(manifest)
        if self.agent in {Agent.CLAUDE, Agent.CODEX}:
            document = load_json_object(destination.path)
            if state == "outdated" and prior is not None:
                document = remove_json_hooks(document or {}, cast(dict, prior.fragment))
            updated = reconcile_json_hooks(document, cast(dict, fragment))
            content = serialize_json(updated)
        else:
            source = _read_optional_regular_file(destination.path)
            if state == "outdated" and prior is not None and source is not None:
                source = serialize_toml(
                    remove_kimi_hooks(source, cast(list[dict], prior.fragment))
                )
            content = serialize_toml(
                reconcile_kimi_hooks(source, cast(list[dict], fragment))
            )
        record = OwnershipRecord(
            self.agent.value,
            AssetKind.HOOK.value,
            name,
            str(destination.path.resolve()),
            fragment_fingerprint(fragment),
            fragment,
        )
        replacements = tuple(
            path
            for path in (destination.path, manifest)
            if path.exists() or path.is_symlink()
        )
        apply_mutation(
            MutationPlan(
                (
                    Write(destination.path, content),
                    Write(manifest, serialize_ownership(record)),
                ),
                replacements,
            )
        )
        return "updated" if state == "outdated" else "installed"

    def _uninstall_shared(
        self, destination: Destination, record: OwnershipRecord, manifest: Path
    ) -> None:
        state, _ = self._inspect_shared(destination, record.name, record.fragment)
        if state != "current":
            raise ConflictError(
                f"hook is not an intact agent-router installation: {destination.path}"
            )
        if self.agent in {Agent.CLAUDE, Agent.CODEX}:
            document = load_json_object(destination.path)
            if document is None:
                raise ConflictError(f"hook destination is absent: {destination.path}")
            content = serialize_json(
                remove_json_hooks(document, cast(dict, record.fragment))
            )
        else:
            source = _read_optional_regular_file(destination.path)
            if source is None:
                raise ConflictError(f"hook destination is absent: {destination.path}")
            content = serialize_toml(
                remove_kimi_hooks(source, cast(list[dict], record.fragment))
            )
        apply_mutation(
            MutationPlan(
                (Write(destination.path, content),),
                (destination.path, manifest),
            )
        )

    def _shared_fragment_present(
        self, destination: Destination, fragment: object
    ) -> bool:
        if not destination.path.exists() and not destination.path.is_symlink():
            return False
        if self.agent in {Agent.CLAUDE, Agent.CODEX}:
            document = load_json_object(destination.path)
            assert document is not None
            try:
                remove_json_hooks(document, cast(dict, fragment))
            except HookDocumentError as error:
                if "missing or modified" in str(error):
                    return False
                raise
            return True
        source = _read_optional_regular_file(destination.path)
        assert source is not None
        try:
            remove_kimi_hooks(source, cast(list[dict], fragment))
        except HookDocumentError as error:
            if "missing or modified" in str(error):
                return False
            raise
        return True

    def _require_record(
        self, path: Path, kind: AssetKind, name: str, destination: Destination
    ) -> OwnershipRecord:
        try:
            record = load_ownership(path)
        except OwnershipError as error:
            raise ConflictError(str(error)) from error
        if (
            record is None
            or record.agent != self.agent.value
            or record.kind != kind.value
            or record.name != name
            or record.destination != str(destination.path.resolve())
        ):
            raise ConflictError(
                f"{kind.value} {name!r} was not installed by agent-router at {destination.path}"
            )
        if kind is AssetKind.HOOK:
            if destination.shared_config:
                expected_type = (
                    dict if self.agent in {Agent.CLAUDE, Agent.CODEX} else list
                )
                if not isinstance(record.fragment, expected_type):
                    raise ConflictError("hook ownership fragment is invalid")
            else:
                details = record.fragment
                if not isinstance(details, dict):
                    raise ConflictError("hook ownership projection is invalid")
                target_name = details.get("target_name")
                if (
                    not isinstance(target_name, str)
                    or not target_name
                    or Path(target_name).name != target_name
                    or details.get("target_type") not in {"file", "directory"}
                    or (
                        details.get("fingerprint_name") is not None
                        and not isinstance(details.get("fingerprint_name"), str)
                    )
                ):
                    raise ConflictError("hook ownership projection is invalid")
        return record

    def _result(
        self,
        operation: str,
        kind: AssetKind,
        name: str,
        scope: Scope,
        destination: Destination,
        status: str,
        compatible_agents: frozenset[Agent] = frozenset(),
        converted: bool = False,
    ) -> LifecycleResult:
        return LifecycleResult(
            operation,
            kind,
            name,
            self.agent,
            scope,
            destination.path,
            status,
            tuple(sorted(compatible_agents, key=lambda agent: agent.value)),
            converted,
        )


def _fingerprint_path(path: Path, *, fingerprint_name: str | None = None) -> str:
    if path.is_symlink():
        raise AssetError(f"managed content is a symbolic link: {path}")
    if path.is_dir():
        return fingerprint_asset(collect_asset_tree(path))
    if path.is_file():
        return fingerprint_asset(
            (AssetFile(fingerprint_name or path.name, path.read_bytes()),)
        )
    raise AssetError(f"managed content is not regular: {path}")


def _read_optional_regular_file(path: Path) -> bytes | None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise HookDocumentError(f"hook destination is not a regular file: {path}")
    return path.read_bytes()
