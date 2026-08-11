from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import cast

from agent_router.core.assets import Hook, Skill, fragment_fingerprint
from agent_router.core.models import (
    Agent,
    AssetKind,
    ConflictError,
    HookTransition,
    LifecycleResult,
    InvalidAssetError,
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
from agent_router.utils.mutation import (
    DirectoryProjection,
    MutationPlan,
    RelativeWrite,
    Write,
    apply_mutation,
)
from agent_router.utils.native_hooks import (
    HookFragmentState,
    HookDocumentError,
    convert_portable_command_hooks,
    load_json_object,
    probe_json_hooks,
    probe_kimi_hooks,
    reconcile_json_hooks,
    reconcile_kimi_hooks,
    remove_json_hooks,
    remove_kimi_hooks,
    serialize_json,
    serialize_toml,
)
from agent_router.utils.ownership import (
    OwnershipEvidence,
    OwnershipError,
    OwnershipRecord,
    classify_ownership,
    load_ownership_evidence,
    serialize_ownership,
)
from agent_router.utils.process import ProcessRunner, run_process
from agent_router.utils.router_state import (
    RouterStateError,
    StateLocations,
    ownership_locations,
    resolve_state_root,
)
from agent_router.utils.gitignore import (
    GitIgnoreError,
    GitIgnorePlan,
    GitIgnorePolicy,
    plan_gitignore,
    verify_gitignore,
)


@dataclass(frozen=True, slots=True)
class _HookReconciliation:
    status: str
    transition: HookTransition | None
    manifest: Path
    predecessor: Hook | None = None
    record: OwnershipRecord | None = None
    shared_source: object | None = None


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
        self._process_runner = process_runner
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
            resolved,
            AssetKind.SKILL,
            skill.name,
            target,
            skill.fingerprint,
            self._ownership_locations(
                resolved, AssetKind.SKILL, skill.name, selected_scope, project_root
            ),
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
        locations = self._ownership_locations(
            resolved, AssetKind.SKILL, skill.name, selected_scope, project_root
        )
        state, evidence = self._inspect_dedicated(
            resolved,
            AssetKind.SKILL,
            skill.name,
            target,
            skill.fingerprint,
            locations,
        )
        if state in {"unmanaged", "conflict"}:
            raise ConflictError(f"conflicting skill destination: {target}")
        if state == "current" and evidence.source == "current":
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
        if state == "current":
            apply_mutation(
                MutationPlan(
                    (Write(locations.current, serialize_ownership(record)),),
                    (locations.legacy,),
                    prune_empty=self._legacy_prune(locations, evidence),
                )
            )
            return self._result(
                "install",
                AssetKind.SKILL,
                skill.name,
                selected_scope,
                resolved,
                "updated",
                skill.compatible_agents,
            )
        writes = tuple(
            Write(target.joinpath(*item.relative_path.split("/")), item.content)
            for item in skill.files
        ) + (Write(locations.current, serialize_ownership(record)),)
        replacements = ((target,) if state == "outdated" else ()) + (
            (locations.legacy,)
            if evidence.source in {"legacy", "duplicate"}
            else ()
        )
        apply_mutation(
            MutationPlan(
                writes,
                replacements,
                prune_empty=self._legacy_prune(locations, evidence),
            )
        )
        return self._result(
            "install",
            AssetKind.SKILL,
            skill.name,
            selected_scope,
            resolved,
            "updated"
            if state == "outdated" or evidence.source in {"legacy", "duplicate"}
            else "installed",
            skill.compatible_agents,
        )

    def update_skill(
        self,
        skill: Skill,
        *,
        scope: Scope = Scope.PROJECT,
        project_root: str | Path | None = None,
        destination: str | Path | None = None,
        ignore_policy: GitIgnorePolicy = GitIgnorePolicy(),
    ) -> LifecycleResult:
        selected_scope = Scope(scope)
        if selected_scope is not Scope.PROJECT or project_root is None:
            raise UnsupportedScopeError(
                "skill update requires project scope and an explicit project root"
            )
        if self.agent not in skill.compatible_agents:
            raise UnsupportedAssetError(
                f"skill {skill.name!r} is not natively compatible with {self.agent.value}"
            )
        resolved = self._destination(
            AssetKind.SKILL, selected_scope, project_root, destination
        )
        target = resolved.path / skill.name
        if target.is_symlink() or not target.is_dir():
            raise ConflictError(
                f"skill update target is not an existing regular directory: {target}"
            )
        locations = self._ownership_locations(
            resolved, AssetKind.SKILL, skill.name, selected_scope, project_root
        )
        try:
            evidence = load_ownership_evidence(locations)
        except OwnershipError as error:
            raise ConflictError(str(error)) from error
        if evidence.record is not None and not self._record_matches(
            evidence.record, AssetKind.SKILL, skill.name, resolved
        ):
            raise ConflictError(f"conflicting skill ownership state: {target}")

        state_root = self._state_root(selected_scope, project_root)
        try:
            ignore = plan_gitignore(
                project_root=Path(project_root),
                target=target,
                state_root=state_root,
                policy=ignore_policy,
                runner=self._process_runner,
            )
        except GitIgnoreError as error:
            raise InvalidAssetError(str(error)) from error
        try:
            current_fingerprint = _fingerprint_path(target)
        except (AssetError, OSError, ValueError) as error:
            raise ConflictError(f"unsafe skill update target: {target}") from error
        record = OwnershipRecord(
            self.agent.value,
            AssetKind.SKILL.value,
            skill.name,
            str(resolved.path.resolve()),
            skill.fingerprint,
            {"target_name": skill.name, "target_type": "directory"},
        )
        writes: tuple[Write, ...] = (
            Write(locations.current, serialize_ownership(record)),
        )
        checks = ()
        if ignore is not None:
            if ignore.content is not None:
                writes += (Write(ignore.ignore_file, ignore.content),)
            checks = (self._gitignore_verification(ignore),)
        projection = (
            ()
            if current_fingerprint == skill.fingerprint
            else (
                DirectoryProjection(
                    target,
                    tuple(
                        RelativeWrite(PurePosixPath(item.relative_path), item.content)
                        for item in skill.files
                    ),
                ),
            )
        )
        replacements = (
            (locations.legacy,)
            if evidence.source in {"legacy", "duplicate"}
            else ()
        )
        try:
            apply_mutation(
                MutationPlan(
                    writes,
                    replacements,
                    projections=projection,
                    prune_empty=self._legacy_prune(locations, evidence),
                    before_projection_swap=checks,
                )
            )
        except GitIgnoreError as error:
            raise InvalidAssetError(str(error)) from error
        return self._result(
            "update",
            AssetKind.SKILL,
            skill.name,
            selected_scope,
            resolved,
            "no-op" if not projection else "updated",
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
        locations = self._ownership_locations(
            resolved, AssetKind.SKILL, name, selected_scope, project_root
        )
        evidence = self._require_record(locations, AssetKind.SKILL, name, resolved)
        record = evidence.record
        assert record is not None
        target = resolved.path / name
        state, _ = self._inspect_dedicated(
            resolved,
            AssetKind.SKILL,
            name,
            target,
            record.fingerprint,
            locations,
        )
        if state != "current":
            raise ConflictError(
                f"skill is not an intact agent-router installation: {target}"
            )
        apply_mutation(
            MutationPlan(
                (),
                (target,)
                + tuple(
                    path
                    for path in (locations.current, locations.legacy)
                    if path.exists() or path.is_symlink()
                ),
                prune_empty=self._legacy_prune(locations, evidence),
            )
        )
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
        predecessors: Sequence[Hook] = (),
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
        selected_predecessors = self._validate_hook_predecessors(
            hook, predecessors, resolved, fragment
        )
        locations = self._ownership_locations(
            resolved, AssetKind.HOOK, hook.name, selected_scope, project_root
        )
        if resolved.shared_config:
            analysis = self._inspect_shared_hook(
                resolved, hook, fragment, selected_predecessors, locations
            )
            state = analysis.status
            transition = analysis.transition
        else:
            analysis = self._inspect_dedicated_hook(
                resolved, hook, selected_predecessors, locations
            )
            state = analysis.status
            transition = analysis.transition
        return self._result(
            "inspect",
            AssetKind.HOOK,
            hook.name,
            selected_scope,
            resolved,
            state,
            hook.compatible_agents,
            converted,
            transition,
        )

    def install_hook(
        self,
        hook: Hook,
        *,
        scope: Scope = Scope.USER,
        project_root: str | Path | None = None,
        destination: str | Path | None = None,
        allow_conversion: bool = False,
        predecessors: Sequence[Hook] = (),
    ) -> LifecycleResult:
        selected_scope = Scope(scope)
        resolved = self._destination(
            AssetKind.HOOK, selected_scope, project_root, destination
        )
        fragment, converted = self._hook_fragment(hook, allow_conversion)
        selected_predecessors = self._validate_hook_predecessors(
            hook, predecessors, resolved, fragment
        )
        locations = self._ownership_locations(
            resolved, AssetKind.HOOK, hook.name, selected_scope, project_root
        )
        if resolved.shared_config:
            state, transition = self._install_shared(
                resolved, hook, fragment, selected_predecessors, locations
            )
        else:
            state, transition = self._install_hook_projection(
                resolved, hook, selected_predecessors, locations
            )
        return self._result(
            "install",
            AssetKind.HOOK,
            hook.name,
            selected_scope,
            resolved,
            state,
            hook.compatible_agents,
            converted,
            transition,
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
        locations = self._ownership_locations(
            resolved, AssetKind.HOOK, name, selected_scope, project_root
        )
        evidence = self._require_record(locations, AssetKind.HOOK, name, resolved)
        record = evidence.record
        assert record is not None
        state_paths = tuple(
            path
            for path in (locations.current, locations.legacy)
            if path.exists() or path.is_symlink()
        )
        if resolved.shared_config:
            transition = self._uninstall_shared(
                resolved,
                record,
                state_paths,
                self._legacy_prune(locations, evidence),
            )
        else:
            details = cast(dict[str, object], record.fragment)
            target = resolved.path / str(details["target_name"])
            if not target.exists() and not target.is_symlink():
                apply_mutation(
                    MutationPlan(
                        (),
                        state_paths,
                        prune_empty=self._legacy_prune(locations, evidence),
                    )
                )
                transition = HookTransition.OWNED_REMOVED
            else:
                try:
                    actual = _fingerprint_path(
                        target,
                        fingerprint_name=cast(
                            str | None, details.get("fingerprint_name")
                        ),
                    )
                except (AssetError, OSError, ValueError) as error:
                    raise ConflictError(
                        f"hook is not an intact agent-router installation: {target}"
                    ) from error
                if actual != record.fingerprint:
                    raise ConflictError(
                        f"hook is not an intact agent-router installation: {target}"
                    )
                apply_mutation(
                    MutationPlan(
                        (),
                        (target,) + state_paths,
                        prune_empty=self._legacy_prune(locations, evidence),
                    )
                )
                transition = None
        return self._result(
            "uninstall",
            AssetKind.HOOK,
            name,
            selected_scope,
            resolved,
            "removed",
            hook_transition=transition,
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

    def _state_root(
        self, scope: Scope, project_root: str | Path | None
    ) -> Path:
        try:
            return resolve_state_root(
                scope.value,
                home=self.home,
                project_root=(
                    Path(project_root).resolve() if project_root is not None else None
                ),
            )
        except RouterStateError as error:
            raise UnsupportedScopeError(str(error)) from error

    def _ownership_locations(
        self,
        destination: Destination,
        kind: AssetKind,
        name: str,
        scope: Scope,
        project_root: str | Path | None,
    ) -> StateLocations:
        try:
            return ownership_locations(
                state_root=self._state_root(scope, project_root),
                destination=destination,
                agent=self.agent.value,
                kind=kind.value,
                name=name,
            )
        except RouterStateError as error:
            raise UnsupportedScopeError(str(error)) from error

    def _gitignore_verification(self, plan: GitIgnorePlan) -> Callable[[], None]:
        return lambda: verify_gitignore(plan, runner=self._process_runner)

    def _legacy_prune(
        self, locations: StateLocations, evidence: OwnershipEvidence
    ) -> tuple[Path, ...]:
        if evidence.source not in {"legacy", "duplicate"}:
            return ()
        return (locations.legacy.parent, locations.legacy.parent.parent)

    def _record_matches(
        self,
        record: OwnershipRecord,
        kind: AssetKind,
        name: str,
        destination: Destination,
    ) -> bool:
        return (
            record.agent == self.agent.value
            and record.kind == kind.value
            and record.name == name
            and record.destination == str(destination.path.resolve())
        )

    def _inspect_dedicated(
        self,
        destination: Destination,
        kind: AssetKind,
        name: str,
        target: Path,
        expected_fingerprint: str,
        locations: StateLocations,
        *,
        fingerprint_name: str | None = None,
    ) -> tuple[str, OwnershipEvidence]:
        evidence = OwnershipEvidence(None, locations, "none")
        try:
            evidence = load_ownership_evidence(locations)
            present = target.exists() or target.is_symlink()
            actual = (
                _fingerprint_path(target, fingerprint_name=fingerprint_name)
                if present
                else None
            )
            state = classify_ownership(
                evidence.record,
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
        return state, evidence

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

    def _validate_hook_predecessors(
        self,
        current: Hook,
        predecessors: Sequence[Hook],
        destination: Destination,
        current_fragment: object,
    ) -> tuple[Hook, ...]:
        selected = tuple(predecessors)
        identities: set[object] = set()
        current_identity: object
        if destination.shared_config:
            current_identity = fragment_fingerprint(current_fragment)
        else:
            current_target, current_fingerprint, _ = self._hook_projection(
                destination, current
            )
            current_identity = (current_target, current_fingerprint)
        for predecessor in selected:
            if self.agent not in predecessor.compatible_agents:
                raise UnsupportedAssetError(
                    f"predecessor {predecessor.name!r} is not natively compatible "
                    f"with {self.agent.value}"
                )
            if destination.shared_config:
                predecessor_fragment, converted = self._hook_fragment(
                    predecessor, False
                )
                assert not converted
                identity = fragment_fingerprint(predecessor_fragment)
            else:
                target, fingerprint, _ = self._hook_projection(
                    destination, predecessor
                )
                identity = (target, fingerprint)
            if identity == current_identity or identity in identities:
                raise UnsupportedAssetError(
                    "hook predecessors must have distinct exact native identities"
                )
            identities.add(identity)
        return selected

    def _inspect_dedicated_hook(
        self,
        destination: Destination,
        current: Hook,
        predecessors: Sequence[Hook],
        locations: StateLocations,
    ) -> _HookReconciliation:
        manifest = locations.current
        try:
            evidence = load_ownership_evidence(locations)
            record = evidence.record
            if record is not None and (
                record.agent != self.agent.value
                or record.kind != AssetKind.HOOK.value
                or record.name != current.name
                or record.destination != str(destination.path.resolve())
            ):
                return _HookReconciliation("conflict", None, manifest)

            target, expected, fingerprint_name = self._hook_projection(
                destination, current
            )
            projections: list[tuple[str, Path, str, str | None]] = [
                ("current", target, expected, fingerprint_name)
            ]
            for index, predecessor in enumerate(predecessors):
                predecessor_target, predecessor_fingerprint, predecessor_name = (
                    self._hook_projection(destination, predecessor)
                )
                projections.append(
                    (
                        f"predecessor:{index}",
                        predecessor_target,
                        predecessor_fingerprint,
                        predecessor_name,
                    )
                )
            if record is not None:
                details = self._dedicated_record_details(record)
                projections.append(
                    (
                        "record",
                        destination.path / details["target_name"],
                        record.fingerprint,
                        details["fingerprint_name"],
                    )
                )

            exact: set[str] = set()
            for candidate in {projection[1] for projection in projections}:
                if not candidate.exists() and not candidate.is_symlink():
                    continue
                matched = False
                for label, path, fingerprint, name in projections:
                    if path != candidate:
                        continue
                    if _fingerprint_path(candidate, fingerprint_name=name) == fingerprint:
                        exact.add(label)
                        matched = True
                if not matched:
                    return _HookReconciliation("conflict", None, manifest)

            present_predecessors = tuple(
                predecessor
                for index, predecessor in enumerate(predecessors)
                if f"predecessor:{index}" in exact
            )
            if len(present_predecessors) > 1:
                return _HookReconciliation("conflict", None, manifest)
            current_present = "current" in exact
            if record is None:
                if current_present:
                    status = "unmanaged"
                    transition = None
                    predecessor = None
                elif present_predecessors:
                    status = "outdated"
                    transition = HookTransition.LEGACY_REPLACED
                    predecessor = present_predecessors[0]
                else:
                    status = "absent"
                    transition = None
                    predecessor = None
                return _HookReconciliation(
                    status, transition, manifest, predecessor, None
                )

            if "record" not in exact:
                if current_present or present_predecessors:
                    return _HookReconciliation("conflict", None, manifest)
                return _HookReconciliation(
                    "outdated",
                    HookTransition.OWNED_RESTORED,
                    manifest,
                    None,
                    record,
                )
            record_details = self._dedicated_record_details(record)
            record_target = destination.path / record_details["target_name"]
            if (
                record.fingerprint == expected
                and record_target == target
                and current_present
            ):
                if present_predecessors:
                    return _HookReconciliation(
                        "outdated",
                        HookTransition.LEGACY_PRUNED,
                        manifest,
                        present_predecessors[0],
                        record,
                    )
                return _HookReconciliation("current", None, manifest, None, record)
            if present_predecessors:
                return _HookReconciliation("conflict", None, manifest)
            return _HookReconciliation("outdated", None, manifest, None, record)
        except (AssetError, OwnershipError, OSError, ValueError, TypeError):
            return _HookReconciliation("conflict", None, manifest)

    def _install_hook_projection(
        self,
        destination: Destination,
        hook: Hook,
        predecessors: Sequence[Hook],
        locations: StateLocations,
    ) -> tuple[str, HookTransition | None]:
        target, expected, fingerprint_name = self._hook_projection(destination, hook)
        analysis = self._inspect_dedicated_hook(
            destination, hook, predecessors, locations
        )
        if analysis.status in {"unmanaged", "conflict"}:
            raise ConflictError(f"conflicting hook destination: {target}")
        legacy_present = locations.legacy.exists() or locations.legacy.is_symlink()
        if analysis.status == "current" and not legacy_present:
            return "no-op", None
        if analysis.status == "current":
            assert analysis.record is not None
            evidence = OwnershipEvidence(
                analysis.record, locations, "legacy"
            )
            apply_mutation(
                MutationPlan(
                    (
                        Write(
                            locations.current,
                            serialize_ownership(analysis.record),
                        ),
                    ),
                    (locations.legacy,),
                    prune_empty=self._legacy_prune(locations, evidence),
                )
            )
            return "updated", None
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
        writes += (Write(analysis.manifest, serialize_ownership(record)),)
        replacements: set[Path] = set()
        if target.exists() or target.is_symlink():
            replacements.add(target)
        if analysis.predecessor is not None:
            predecessor_target, _, _ = self._hook_projection(
                destination, analysis.predecessor
            )
            replacements.add(predecessor_target)
        if (
            analysis.record is not None
            and analysis.transition is not HookTransition.OWNED_RESTORED
        ):
            details = self._dedicated_record_details(analysis.record)
            replacements.add(destination.path / details["target_name"])
        if legacy_present:
            replacements.add(locations.legacy)
        evidence = OwnershipEvidence(
            analysis.record,
            locations,
            "legacy" if legacy_present else "current",
        )
        apply_mutation(
            MutationPlan(
                writes,
                tuple(sorted(replacements)),
                prune_empty=self._legacy_prune(locations, evidence),
            )
        )
        return (
            "updated"
            if analysis.status == "outdated" or legacy_present
            else "installed",
            analysis.transition,
        )

    def _dedicated_record_details(
        self, record: OwnershipRecord
    ) -> dict[str, str | None]:
        details = record.fragment
        if not isinstance(details, dict):
            raise ValueError("hook ownership projection is invalid")
        target_name = details.get("target_name")
        fingerprint_name = details.get("fingerprint_name")
        if (
            not isinstance(target_name, str)
            or not target_name
            or Path(target_name).name != target_name
            or details.get("target_type") not in {"file", "directory"}
            or (fingerprint_name is not None and not isinstance(fingerprint_name, str))
        ):
            raise ValueError("hook ownership projection is invalid")
        return {
            "target_name": target_name,
            "fingerprint_name": cast(str | None, fingerprint_name),
        }

    def _inspect_shared_hook(
        self,
        destination: Destination,
        current: Hook,
        expected_fragment: object,
        predecessors: Sequence[Hook],
        locations: StateLocations,
    ) -> _HookReconciliation:
        manifest = locations.current
        try:
            record = load_ownership_evidence(locations).record
            if record is not None and (
                record.agent != self.agent.value
                or record.kind != AssetKind.HOOK.value
                or record.name != current.name
                or record.destination != str(destination.path.resolve())
            ):
                return _HookReconciliation("conflict", None, manifest)
            source = self._load_shared_source(destination)
            predecessor_fragments = tuple(
                self._hook_fragment(predecessor, False)[0]
                for predecessor in predecessors
            )
            fragments: dict[str, object] = {
                fragment_fingerprint(expected_fragment): expected_fragment
            }
            if record is not None:
                if not isinstance(
                    record.fragment,
                    dict if self.agent in {Agent.CLAUDE, Agent.CODEX} else list,
                ):
                    return _HookReconciliation("conflict", None, manifest)
                fragments[fragment_fingerprint(record.fragment)] = record.fragment
            for fragment in predecessor_fragments:
                fragments[fragment_fingerprint(fragment)] = fragment

            counts: dict[str, int] = {}
            residual = source
            ordered_fragments = sorted(
                fragments.items(),
                key=lambda item: self._shared_fragment_size(item[1]),
                reverse=True,
            )
            for fingerprint, fragment in ordered_fragments:
                count, remaining = self._shared_exact_count(residual, fragment)
                if count > 1:
                    return _HookReconciliation("conflict", None, manifest)
                counts[fingerprint] = count
                if count == 1:
                    residual = remaining

            for fingerprint, fragment in fragments.items():
                if counts[fingerprint] == 0 and self._probe_shared_fragment(
                    residual, fragment
                ) is HookFragmentState.CONFLICT:
                    return _HookReconciliation("conflict", None, manifest)

            current_fingerprint = fragment_fingerprint(expected_fragment)
            current_present = counts[current_fingerprint] == 1
            present_predecessors = tuple(
                predecessor
                for predecessor, fragment in zip(
                    predecessors, predecessor_fragments, strict=True
                )
                if counts[fragment_fingerprint(fragment)] == 1
            )
            if len(present_predecessors) > 1:
                return _HookReconciliation("conflict", None, manifest)

            if record is None:
                if current_present:
                    status = "unmanaged"
                    transition = None
                    predecessor = None
                elif present_predecessors:
                    status = "outdated"
                    transition = HookTransition.LEGACY_REPLACED
                    predecessor = present_predecessors[0]
                else:
                    status = "absent"
                    transition = None
                    predecessor = None
                return _HookReconciliation(
                    status, transition, manifest, predecessor, None, source
                )

            record_present = counts[fragment_fingerprint(record.fragment)] == 1
            if not record_present:
                if current_present or present_predecessors:
                    return _HookReconciliation("conflict", None, manifest)
                return _HookReconciliation(
                    "outdated",
                    HookTransition.OWNED_RESTORED,
                    manifest,
                    None,
                    record,
                    source,
                )
            if record.fingerprint == current_fingerprint and current_present:
                if present_predecessors:
                    return _HookReconciliation(
                        "outdated",
                        HookTransition.LEGACY_PRUNED,
                        manifest,
                        present_predecessors[0],
                        record,
                        source,
                    )
                return _HookReconciliation(
                    "current", None, manifest, None, record, source
                )
            if present_predecessors:
                return _HookReconciliation("conflict", None, manifest)
            return _HookReconciliation(
                "outdated", None, manifest, None, record, source
            )
        except (OwnershipError, HookDocumentError, OSError, ValueError, TypeError):
            return _HookReconciliation("conflict", None, manifest)

    def _install_shared(
        self,
        destination: Destination,
        hook: Hook,
        fragment: object,
        predecessors: Sequence[Hook],
        locations: StateLocations,
    ) -> tuple[str, HookTransition | None]:
        analysis = self._inspect_shared_hook(
            destination, hook, fragment, predecessors, locations
        )
        if analysis.status in {"unmanaged", "conflict"}:
            raise ConflictError(f"conflicting hook destination: {destination.path}")
        legacy_present = locations.legacy.exists() or locations.legacy.is_symlink()
        if analysis.status == "current" and not legacy_present:
            return "no-op", None
        if analysis.status == "current":
            assert analysis.record is not None
            evidence = OwnershipEvidence(
                analysis.record, locations, "legacy"
            )
            apply_mutation(
                MutationPlan(
                    (
                        Write(
                            locations.current,
                            serialize_ownership(analysis.record),
                        ),
                    ),
                    (locations.legacy,),
                    prune_empty=self._legacy_prune(locations, evidence),
                )
            )
            return "updated", None
        source = analysis.shared_source
        removed: set[str] = set()
        if analysis.predecessor is not None:
            predecessor_fragment, _ = self._hook_fragment(
                analysis.predecessor, False
            )
            source = self._remove_shared_fragment(source, predecessor_fragment)
            removed.add(fragment_fingerprint(predecessor_fragment))
        prior = analysis.record
        if (
            prior is not None
            and analysis.transition is not HookTransition.OWNED_RESTORED
            and prior.fingerprint != fragment_fingerprint(fragment)
            and prior.fingerprint not in removed
        ):
            source = self._remove_shared_fragment(source, prior.fragment)
        if self.agent in {Agent.CLAUDE, Agent.CODEX}:
            updated = reconcile_json_hooks(cast(dict | None, source), cast(dict, fragment))
            content = serialize_json(updated)
        else:
            content = serialize_toml(
                reconcile_kimi_hooks(cast(bytes | None, source), cast(list[dict], fragment))
            )
        record = OwnershipRecord(
            self.agent.value,
            AssetKind.HOOK.value,
            hook.name,
            str(destination.path.resolve()),
            fragment_fingerprint(fragment),
            fragment,
        )
        replacements = tuple(
            path
            for path in (destination.path, locations.legacy)
            if path.exists() or path.is_symlink()
        )
        evidence = OwnershipEvidence(
            analysis.record,
            locations,
            "legacy" if legacy_present else "current",
        )
        apply_mutation(
            MutationPlan(
                (
                    Write(destination.path, content),
                    Write(analysis.manifest, serialize_ownership(record)),
                ),
                replacements,
                prune_empty=self._legacy_prune(locations, evidence),
            )
        )
        return (
            "updated"
            if analysis.status == "outdated" or legacy_present
            else "installed",
            analysis.transition,
        )

    def _load_shared_source(self, destination: Destination) -> object | None:
        if self.agent in {Agent.CLAUDE, Agent.CODEX}:
            return load_json_object(destination.path)
        return _read_optional_regular_file(destination.path)

    def _shared_exact_count(
        self, source: object | None, fragment: object
    ) -> tuple[int, object | None]:
        try:
            once = self._remove_shared_fragment(source, fragment)
        except HookDocumentError:
            return 0, source
        try:
            twice = self._remove_shared_fragment(once, fragment)
        except HookDocumentError:
            return 1, once
        return 2, twice

    def _shared_fragment_size(self, fragment: object) -> int:
        if isinstance(fragment, dict):
            return sum(len(groups) for groups in fragment.values())
        if isinstance(fragment, list):
            return len(fragment)
        raise TypeError("hook fragment has unsupported native shape")

    def _remove_shared_fragment(
        self, source: object | None, fragment: object
    ) -> object:
        if self.agent in {Agent.CLAUDE, Agent.CODEX}:
            return remove_json_hooks(cast(dict, source or {}), cast(dict, fragment))
        return serialize_toml(
            remove_kimi_hooks(cast(bytes, source or b""), cast(list[dict], fragment))
        )

    def _probe_shared_fragment(
        self, source: object | None, fragment: object
    ) -> HookFragmentState:
        if self.agent in {Agent.CLAUDE, Agent.CODEX}:
            return probe_json_hooks(cast(dict | None, source), cast(dict, fragment))
        return probe_kimi_hooks(cast(bytes | None, source), cast(list[dict], fragment))

    def _uninstall_shared(
        self,
        destination: Destination,
        record: OwnershipRecord,
        state_paths: tuple[Path, ...],
        prune_empty: tuple[Path, ...],
    ) -> HookTransition | None:
        source = self._load_shared_source(destination)
        count, _ = self._shared_exact_count(source, record.fragment)
        if count == 0:
            if self._probe_shared_fragment(
                source, record.fragment
            ) is not HookFragmentState.ABSENT:
                raise ConflictError(
                    f"hook is not an intact agent-router installation: {destination.path}"
                )
            apply_mutation(
                MutationPlan((), state_paths, prune_empty=prune_empty)
            )
            return HookTransition.OWNED_REMOVED
        if count != 1:
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
                (destination.path,) + state_paths,
                prune_empty=prune_empty,
            )
        )
        return None

    def _require_record(
        self,
        locations: StateLocations,
        kind: AssetKind,
        name: str,
        destination: Destination,
    ) -> OwnershipEvidence:
        try:
            evidence = load_ownership_evidence(locations)
            record = evidence.record
        except OwnershipError as error:
            raise ConflictError(str(error)) from error
        if (
            record is None
            or not self._record_matches(record, kind, name, destination)
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
        return evidence

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
        hook_transition: HookTransition | None = None,
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
            hook_transition,
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
