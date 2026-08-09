from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import PurePath

from behave import given, then, when

from agent_router import (
    Agent,
    ArtifactEffectiveState,
    ArtifactManifest,
    ArtifactPolicy,
    PluginActivation,
)
from agent_router.utils.artifact_paths import ArtifactPathError
from agent_router.utils.plugin_state import load_plugin_state, plugin_state_path
from features.support.plugins import (
    FakeNativeManager,
    PathArtifactExtension,
    plugin_router,
    ref,
)


@given("an agent with installed, available, cached, and orphaned plugin material")
def installed_available_and_stale(context) -> None:
    context.native = FakeNativeManager(context.destination)
    context.native.add()
    context.native.available.append(context.native.add("available@configured"))
    context.native.installed.pop()
    (context.destination / "cache-only").mkdir(parents=True)
    (context.destination / "orphan-only").mkdir()
    context.router = plugin_router(context, Agent.CODEX)
    context.before_paths = sorted(path.relative_to(context.destination) for path in context.destination.rglob("*"))


@when("I discover plugins without requesting available entries")
def discover_installed(context) -> None:
    context.records = context.router.discover_plugins()


@then("only plugins in the agent's authoritative installed state are returned")
def only_authoritative_installed(context) -> None:
    assert [item.ref.native_ref for item in context.records] == ["review@configured"]


@then("discovery does not mutate native or router state")
def discovery_read_only(context) -> None:
    after = sorted(path.relative_to(context.destination) for path in context.destination.rglob("*"))
    assert after == context.before_paths
    assert not plugin_state_path(context.destination).exists()


@given("an agent with configured and unconfigured plugin catalogs")
def configured_catalogs(context) -> None:
    context.native = FakeNativeManager(context.destination)
    context.native.available.append(
        context.native.add("configured-only@configured", source="configured")
    )
    context.native.installed.pop()
    context.unconfigured = "unconfigured-only@public"
    context.router = plugin_router(context, Agent.CLAUDE)


@when("I explicitly include available plugins in discovery")
def discover_available(context) -> None:
    context.records = context.router.discover_plugins(include_available=True)


@then("available entries come only from the agent's configured catalogs")
def configured_only(context) -> None:
    refs = {item.ref.native_ref for item in context.records}
    assert "configured-only@configured" in refs
    assert context.unconfigured not in refs


@then("no public gallery is searched or administered")
def no_gallery_admin(context) -> None:
    assert all("marketplace" not in request.argv for request in context.native.calls)


@given("the same native plugin is installed in two supported scopes")
def same_plugin_two_scopes(context) -> None:
    context.native = FakeNativeManager(context.destination)
    context.native.add(scope="user")
    context.native.add(scope="project")
    context.router = plugin_router(context, Agent.CLAUDE)


@when("I discover the plugin installations")
def discover_scopes(context) -> None:
    context.records = context.router.discover_plugins()


@then("each record has a distinct opaque PluginRef retaining agent, native reference, scope, and source qualifier")
def exact_refs(context) -> None:
    assert {item.ref.scope for item in context.records} == {"user", "project"}
    assert all(item.ref.native_ref == "review@configured" for item in context.records)
    assert all(item.ref.source == "configured" for item in context.records)


@then("no cross-scope precedence is asserted")
def no_scope_precedence(context) -> None:
    assert len(context.records) == 2


@given("installed and available plugin records with predicted cache locations")
def roots_with_predictions(context) -> None:
    context.native = FakeNativeManager(context.destination)
    context.installed = context.native.add()
    context.available = context.native.add("available@configured")
    context.native.installed.remove(context.available)
    context.native.available.append(context.available)
    context.router = plugin_router(context, Agent.CODEX)


@when("I discover their runtime roots")
def discover_roots(context) -> None:
    context.records = context.router.discover_plugins(include_available=True)


@then("each authoritative materialized installation returns its canonical absolute runtime root")
def installed_root_absolute(context) -> None:
    installed = next(item for item in context.records if item.installed)
    assert installed.runtime_root == context.installed.root.resolve(strict=True)
    assert installed.runtime_root.is_absolute()


@then("every unmaterialized or unverified record returns no runtime root")
def no_predicted_root(context) -> None:
    available = next(item for item in context.records if not item.installed)
    assert available.runtime_root is None


@given("{agent} reports {evidence} for an installed plugin")
def activation_evidence(context, agent: str, evidence: str) -> None:
    context.agent = Agent(agent)
    context.native = FakeNativeManager(context.destination)
    enabled = "disabled" not in evidence
    if context.agent is Agent.KIMI:
        root = context.destination / "managed" / "review"
        root.mkdir(parents=True)
        installed = context.destination / "plugins" / "installed.json"
        installed.parent.mkdir(parents=True)
        installed.write_text(
            json.dumps(
                {
                    "version": 1,
                    "plugins": [
                        {
                            "id": "review",
                            "root": str(root),
                            "source": "local-path",
                            "enabled": enabled,
                            "installedAt": "2026-08-08T00:00:00Z",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
    else:
        native_ref = "npm:review" if context.agent is Agent.PI else "review@configured"
        context.native.add(native_ref, enabled=enabled)
    context.router = plugin_router(context, context.agent)


@when("I discover that plugin")
def discover_activation(context) -> None:
    (context.record,) = context.router.discover_plugins()


@then("its normalized activation is {state}")
def normalized_activation(context, state: str) -> None:
    assert context.record.activation is PluginActivation(state)


@then("the native evidence is retained")
def evidence_retained(context) -> None:
    assert context.record.native_evidence is not None


@given("an explicitly supplied extension with a namespaced ArtifactManifest")
def explicit_extension(context) -> None:
    context.native = FakeNativeManager(context.destination)
    context.plugin = context.native.add()
    context.extension = PathArtifactExtension(
        ArtifactManifest("zpp.traits", "1"), PurePath("traits/example.yaml")
    )


@given("its locator returns a relative artifact path for an eligible plugin")
def relative_artifact(context) -> None:
    artifact = context.plugin.root / "traits" / "example.yaml"
    artifact.parent.mkdir()
    artifact.write_text("domain content is intentionally opaque: [", encoding="utf-8")
    context.artifact = artifact
    context.router = plugin_router(context, Agent.CODEX, extensions=(context.extension,))


@when("I resolve that artifact identifier")
def resolve_identifier(context) -> None:
    try:
        context.statuses = context.router.resolve_artifacts("zpp.traits")
    except Exception as error:  # scenarios assert the public failure
        context.error = error


@then("the locator receives an immutable PluginArtifactContext")
def immutable_context(context) -> None:
    (received,) = context.extension.contexts
    try:
        received.root = context.root  # type: ignore[misc]
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("artifact context is mutable")


@then("the result contains the canonical absolute artifact path and effective status")
def artifact_result(context) -> None:
    (status,) = context.statuses
    assert status.paths == (context.artifact.resolve(strict=True),)
    assert status.effective is ArtifactEffectiveState.ACTIVE


@then("agent-router does not parse the artifact's domain content")
def no_domain_parse(context) -> None:
    assert context.error is None


@given("a registered artifact locator returns a path that escapes through traversal or a symbolic link")
def escaping_locator(context) -> None:
    context.native = FakeNativeManager(context.destination)
    context.native.add()
    (context.destination / "outside.yaml").write_text("outside", encoding="utf-8")
    context.extension = PathArtifactExtension(
        ArtifactManifest("zpp.traits", "1"), PurePath("../../../outside.yaml")
    )
    context.router = plugin_router(context, Agent.CODEX, extensions=(context.extension,))


@then("resolution fails without returning or loading the escaped path")
def escape_rejected(context) -> None:
    assert isinstance(context.error, ArtifactPathError)
    assert not hasattr(context, "statuses")


@given("an eligible plugin contributes two registered artifact identifiers")
def two_artifacts(context) -> None:
    context.native = FakeNativeManager(context.destination)
    plugin = context.native.add()
    for directory in ("traits", "leases"):
        path = plugin.root / directory / "item"
        path.parent.mkdir()
        path.write_text(directory, encoding="utf-8")
    context.extensions = (
        PathArtifactExtension(ArtifactManifest("zpp.traits", "1"), PurePath("traits/item")),
        PathArtifactExtension(ArtifactManifest("openlease.leases", "1"), PurePath("leases/item")),
    )
    context.ref = ref(Agent.CODEX)
    context.router = plugin_router(context, Agent.CODEX, extensions=context.extensions)


@when("I set one artifact policy to disabled")
def disable_one(context) -> None:
    context.disabled = context.router.set_artifact_policy(
        context.ref, "zpp.traits", ArtifactPolicy.DISABLED
    )
    context.other = context.router.artifact_status(context.ref, "openlease.leases")


@then("only that artifact contribution becomes inactive by router policy")
def only_one_inactive(context) -> None:
    assert context.disabled.effective is ArtifactEffectiveState.INACTIVE
    assert context.disabled.reason == "router-disabled"
    assert context.other.effective is ArtifactEffectiveState.ACTIVE


@then("the native plugin and other artifact contribution remain unchanged")
def native_unchanged(context) -> None:
    assert context.native.installed[0].enabled
    assert context.other.paths


@given("a natively disabled plugin with a registered generic artifact")
def disabled_plugin_artifact(context) -> None:
    context.native = FakeNativeManager(context.destination)
    plugin = context.native.add(enabled=False)
    artifact = plugin.root / "traits" / "item"
    artifact.parent.mkdir()
    artifact.write_text("item", encoding="utf-8")
    context.extension = PathArtifactExtension(
        ArtifactManifest("zpp.traits", "1"), PurePath("traits/item")
    )
    context.ref = ref(Agent.CODEX)
    context.router = plugin_router(context, Agent.CODEX, extensions=(context.extension,))


@when("I set that artifact policy to enabled")
def enable_artifact(context) -> None:
    context.status = context.router.set_artifact_policy(
        context.ref, "zpp.traits", ArtifactPolicy.ENABLED
    )


@then("its effective artifact status remains inactive for the native reason")
def native_reason_wins(context) -> None:
    assert context.status.effective is ArtifactEffectiveState.INACTIVE
    assert context.status.reason == "native-disabled"


@then("no artifact path is returned")
def no_artifact_path(context) -> None:
    assert context.status.paths == ()


@given("an installed Pi package with resource-level filtering and a registered generic artifact")
def pi_artifact(context) -> None:
    context.native = FakeNativeManager(context.destination)
    plugin = context.native.add("npm:review")
    artifact = plugin.root / "traits" / "item"
    artifact.parent.mkdir()
    artifact.write_text("item", encoding="utf-8")
    context.extension = PathArtifactExtension(
        ArtifactManifest("zpp.traits", "1"), PurePath("traits/item")
    )
    context.router = plugin_router(context, Agent.PI, extensions=(context.extension,))


@when("I resolve the artifact with inherited policy")
def resolve_inherited(context) -> None:
    (context.status,) = context.router.resolve_artifacts("zpp.traits")


@then("the package is eligible for that generic artifact")
def pi_eligible(context) -> None:
    assert context.status.effective is ArtifactEffectiveState.ACTIVE


@then("its native activation evidence remains partial or unknown")
def pi_evidence_partial(context) -> None:
    assert context.status.ref.agent is Agent.PI
    assert context.extension.contexts[0].plugin.activation in {
        PluginActivation.PARTIAL,
        PluginActivation.UNKNOWN,
    }


@given("a scoped plugin has an explicit artifact policy")
def explicit_policy(context) -> None:
    two_artifacts(context)
    context.router.set_artifact_policy(
        context.ref, "zpp.traits", ArtifactPolicy.ENABLED
    )


@when("its authoritative version and runtime root change")
def move_plugin(context) -> None:
    old = context.native.installed[0]
    context.old_root = old.root
    context.native._move(old)
    new_artifact = old.root / "traits" / "item"
    new_artifact.parent.mkdir()
    new_artifact.write_text("new", encoding="utf-8")
    context.new_artifact = new_artifact
    context.status = context.router.artifact_status(context.ref, "zpp.traits")


@then("the policy remains attached to its stable scoped PluginRef")
def policy_stable(context) -> None:
    assert context.status.policy is ArtifactPolicy.ENABLED
    assert context.status.ref.native_ref == context.ref.native_ref
    assert context.status.ref.scope == context.ref.scope


@then("subsequent resolution returns only the new canonical absolute artifact path")
def only_new_path(context) -> None:
    assert context.status.paths == (context.new_artifact.resolve(strict=True),)
    assert all(not path.is_relative_to(context.old_root) for path in context.status.paths)


@when("I clear that policy override")
def clear_policy(context) -> None:
    context.status = context.router.clear_artifact_policy(context.ref, "zpp.traits")


@then("its persisted override is removed")
def override_removed(context) -> None:
    state = load_plugin_state(plugin_state_path(context.destination))
    assert not state.overrides


@then("its effective artifact policy returns to inherit")
def policy_inherit(context) -> None:
    assert context.status.policy is ArtifactPolicy.INHERIT


@given("a plugin previously contributed a registered artifact")
def previously_contributed(context) -> None:
    explicit_extension(context)
    relative_artifact(context)
    (context.prior,) = context.router.resolve_artifacts("zpp.traits")


@when("the authoritative agent state disables or removes that plugin")
def disable_authoritatively(context) -> None:
    context.native.installed[0].enabled = False
    (context.status,) = context.router.resolve_artifacts("zpp.traits")


@then("subsequent resolution excludes its former artifact paths")
def stale_paths_excluded(context) -> None:
    assert context.prior.paths
    assert context.status.paths == ()


@then("cached files or prior contexts do not remain effective")
def no_stale_context(context) -> None:
    assert context.status.reason == "native-disabled"
    assert len(context.extension.contexts) == 1


@given("two agents expose similarly named plugins")
def two_agents(context) -> None:
    context.codex_native = FakeNativeManager(context.root / "codex")
    context.codex_native.add("review@codex-market")
    context.native = context.codex_native
    context.codex_router = plugin_router(context, Agent.CODEX)
    context.claude_native = FakeNativeManager(context.root / "claude")
    context.claude_native.add("review@claude-market")


@when("I discover both agents independently")
def discover_agents(context) -> None:
    (context.codex_record,) = context.codex_router.discover_plugins()
    context.native = context.claude_native
    context.destination = context.root / "claude"
    context.claude_router = plugin_router(context, Agent.CLAUDE)
    (context.claude_record,) = context.claude_router.discover_plugins()


@then("each plugin remains an independent native record")
def independent_records(context) -> None:
    assert context.codex_record.ref.agent is Agent.CODEX
    assert context.claude_record.ref.agent is Agent.CLAUDE
    assert context.codex_record.ref != context.claude_record.ref


@then("agent-router does not assert cross-agent compatibility or conversion")
def no_conversion(context) -> None:
    assert "compatible_agents" not in context.codex_record.to_dict()
    assert "converted" not in context.claude_record.to_dict()
