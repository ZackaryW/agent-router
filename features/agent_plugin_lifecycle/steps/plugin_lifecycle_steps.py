from __future__ import annotations

from pathlib import PurePath

from behave import given, then, when

from agent_router import (
    Agent,
    ArtifactManifest,
    PluginManagerUnavailableError,
    PluginRef,
    PluginTrustError,
    UnmanagedPluginError,
    UnsupportedPluginLifecycleError,
    UnsupportedScopeError,
)
from agent_router.utils.plugin_state import load_plugin_state, plugin_state_path
from features.support.lifecycle import capture
from features.support.plugins import (
    FakeNativeManager,
    PathArtifactExtension,
    plugin_router,
    ref,
)


def _selected_ref(agent: Agent, scope: str = "user") -> PluginRef:
    native_ref = "npm:review" if agent is Agent.PI else "review@configured"
    return ref(agent, native_ref, scope)


@given("a configured native catalog entry for {agent}")
def configured_entry(context, agent: str) -> None:
    context.agent = Agent(agent)
    context.native = FakeNativeManager(context.destination)
    context.ref = _selected_ref(context.agent)
    context.router = plugin_router(context, context.agent)


@when("I install that plugin in an exact supported scope")
def install_supported(context) -> None:
    capture(context, lambda: context.router.install_plugin(context.ref))


@then("the {agent} native manager is invoked for only that plugin")
def selected_manager_invoked(context, agent: str) -> None:
    mutation = [call for call in context.native.calls if "list" not in call.argv]
    assert mutation
    assert all(context.ref.native_ref in call.argv for call in mutation)
    assert all(call.argv[0] == agent for call in mutation)


@then("authoritative discovery verifies the installed postcondition")
def installed_verified(context) -> None:
    assert context.error is None
    assert context.result.status == "installed"
    assert context.result.verified
    assert context.result.after is not None and context.result.after.installed
    assert sum("list" in call.argv for call in context.native.calls) >= 2


@then("a router ownership receipt is recorded for its scoped PluginRef")
def receipt_recorded(context) -> None:
    state = load_plugin_state(plugin_state_path(context.destination))
    assert len(state.receipts) == 1
    assert state.receipts[0].key.native_ref == context.ref.native_ref
    assert state.receipts[0].key.scope == context.ref.scope


@given("Kimi exposes only interactive plugin lifecycle management")
def kimi_interactive(context) -> None:
    context.agent = Agent.KIMI
    context.native = FakeNativeManager(context.destination)
    context.ref = ref(Agent.KIMI, "review")
    context.router = plugin_router(context, Agent.KIMI)
    context.before = list(context.destination.rglob("*"))


@when("I request Kimi plugin installation, update, or removal")
def mutate_kimi(context) -> None:
    context.errors = []
    for action in (
        lambda: context.router.install_plugin(context.ref),
        lambda: context.router.update_plugin(context.ref),
        lambda: context.router.remove_plugin(context.ref),
    ):
        try:
            action()
        except Exception as error:
            context.errors.append(error)


@then("the operation reports an unsupported lifecycle")
def unsupported_kimi(context) -> None:
    assert len(context.errors) == 3
    assert all(isinstance(error, UnsupportedPluginLifecycleError) for error in context.errors)


@then("no Kimi registry or managed plugin content is changed")
def kimi_unchanged(context) -> None:
    assert list(context.destination.rglob("*")) == context.before
    assert not context.native.calls


@given("one plugin reference is installed in two native scopes")
def owned_two_scopes(context) -> None:
    context.agent = Agent.CLAUDE
    context.native = FakeNativeManager(context.destination)
    context.router = plugin_router(context, context.agent)
    context.user_ref = _selected_ref(context.agent, "user")
    context.project_ref = _selected_ref(context.agent, "project")
    context.router.install_plugin(context.user_ref)
    context.router.install_plugin(context.project_ref)
    context.user_before = next(item.root for item in context.native.installed if item.scope == "user")
    context.native.calls.clear()


@when("I update its router-owned project-scoped installation")
def update_project_scope(context) -> None:
    capture(context, lambda: context.router.update_plugin(context.project_ref))


@then("only the project-scoped PluginRef is passed to the native manager")
def only_project_ref(context) -> None:
    mutations = [call for call in context.native.calls if "list" not in call.argv]
    assert len(mutations) == 1
    assert "project" in mutations[0].argv
    assert context.project_ref.native_ref in mutations[0].argv


@then("the other scoped installation remains unchanged")
def user_unchanged(context) -> None:
    user = next(item for item in context.native.installed if item.scope == "user")
    assert user.root == context.user_before


@given("a plugin lifecycle request names a scope unsupported by the selected agent")
def unsupported_scope(context) -> None:
    context.native = FakeNativeManager(context.destination)
    context.ref = _selected_ref(Agent.CODEX, "project")
    context.router = plugin_router(context, Agent.CODEX)


@when("I preflight the request")
def preflight(context) -> None:
    capture(context, lambda: context.router.install_plugin(context.ref))


@then("the operation reports an unsupported scope")
def reports_scope(context) -> None:
    assert isinstance(context.error, UnsupportedScopeError)


@then("the native manager is not invoked")
def manager_not_invoked(context) -> None:
    assert not context.native.calls


@given("a plugin entry from a catalog already configured in the selected agent")
def catalog_entry(context) -> None:
    configured_entry(context, "claude")


@when("I explicitly install that entry without a trust option")
def install_catalog(context) -> None:
    capture(context, lambda: context.router.install_plugin(context.ref, trust=False))


@then("router preflight accepts the configured source")
def catalog_accepted(context) -> None:
    assert context.error is None
    assert context.result.status == "installed"


@then("native trust and administrative policy remain authoritative")
def native_policy_authoritative(context) -> None:
    assert any("install" in call.argv for call in context.native.calls)


@given("an install request from a direct {source}")
def direct_source(context, source: str) -> None:
    values = {
        "URL": "https://example.test/plugin.zip",
        "Git ref": "git:github.com/team/plugin",
        "local path": "./local-plugin",
    }
    context.native = FakeNativeManager(context.destination)
    context.ref = PluginRef(Agent.PI, values[source], "user")
    context.router = plugin_router(context, Agent.PI)


@when("I install without explicit trust")
def install_untrusted(context) -> None:
    capture(context, lambda: context.router.install_plugin(context.ref))


@then("preflight rejects the request without invoking native mutation")
def trust_rejected(context) -> None:
    assert isinstance(context.error, PluginTrustError)
    assert not context.native.calls


@given("an installed plugin has no valid agent-router ownership receipt")
def unmanaged_install(context) -> None:
    context.native = FakeNativeManager(context.destination)
    context.native.add()
    context.ref = _selected_ref(Agent.CLAUDE)
    context.router = plugin_router(context, Agent.CLAUDE)
    context.native.calls.clear()


@when("I request update or removal")
def mutate_unmanaged(context) -> None:
    capture(context, lambda: context.router.update_plugin(context.ref))


@then("the operation reports unmanaged state")
def reports_unmanaged(context) -> None:
    assert isinstance(context.error, UnmanagedPluginError)


@given("an intact router ownership receipt records an earlier version and root")
def historical_receipt(context) -> None:
    configured_entry(context, "claude")
    context.router.install_plugin(context.ref)
    context.receipt_before = load_plugin_state(plugin_state_path(context.destination)).receipts[0]
    context.native.calls.clear()


@given("authoritative state identifies its successor under the same scoped PluginRef")
def successor_state(context) -> None:
    context.native._move(context.native.installed[0])


@when("I update that plugin")
def update_owned(context) -> None:
    capture(context, lambda: context.router.update_plugin(context.ref))


@then("the historical receipt remains valid ownership evidence")
def historical_valid(context) -> None:
    assert context.error is None
    after = load_plugin_state(plugin_state_path(context.destination)).receipts[0]
    assert after.key == context.receipt_before.key


@then("only the selected plugin is converged and verified")
def selected_converged(context) -> None:
    assert context.result.after.ref.native_ref == context.ref.native_ref
    mutations = [call for call in context.native.calls if "list" not in call.argv]
    assert all(context.ref.native_ref in call.argv for call in mutations)


@given("an owned Codex plugin requires current marketplace metadata")
def owned_codex(context) -> None:
    configured_entry(context, "codex")
    context.router.install_plugin(context.ref)
    context.native.calls.clear()


@given("other marketplaces and plugins also have updates")
def other_updates(context) -> None:
    context.other = context.native.add("other@another-market")


@when("I update the selected plugin")
def update_selected(context) -> None:
    capture(context, lambda: context.router.update_plugin(context.ref))


@then("only its configured owning marketplace is refreshed")
def selected_marketplace(context) -> None:
    upgrades = [call for call in context.native.calls if "upgrade" in call.argv]
    assert len(upgrades) == 1
    assert "configured" in upgrades[0].argv
    assert "another-market" not in upgrades[0].argv


@then("only the selected plugin is converged")
def selected_plugin_only(context) -> None:
    mutations = [call for call in context.native.calls if "list" not in call.argv and "upgrade" not in call.argv]
    assert len(mutations) == 1
    assert context.ref.native_ref in mutations[0].argv
    assert context.other.version == "1.0"


@given("an installed plugin has a valid router ownership receipt")
def owned_plugin(context) -> None:
    configured_entry(context, "claude")
    context.router.install_plugin(context.ref)
    context.unrelated = context.native.add("unrelated@configured")
    context.native.calls.clear()


@when("I remove that scoped plugin")
def remove_owned(context) -> None:
    capture(context, lambda: context.router.remove_plugin(context.ref))


@then("authoritative discovery verifies that exact installation is absent")
def exact_absent(context) -> None:
    assert context.result.status == "removed"
    assert all(item.native_ref != context.ref.native_ref for item in context.native.installed)


@then("only then is its ownership receipt cleared")
def receipt_cleared(context) -> None:
    assert not load_plugin_state(plugin_state_path(context.destination)).receipts


@then("unrelated plugins remain unchanged")
def unrelated_unchanged(context) -> None:
    assert context.unrelated in context.native.installed
    assert context.unrelated.version == "1.0"


@given("a requested plugin already has the requested authoritative installed state")
def converged_install(context) -> None:
    configured_entry(context, "claude")
    context.router.install_plugin(context.ref)
    context.unrelated = context.native.add("unrelated@configured")
    context.snapshot = [(item.native_ref, item.version, item.root) for item in context.native.installed]
    context.native.calls.clear()


@when("I install it again")
def reinstall(context) -> None:
    capture(context, lambda: context.router.install_plugin(context.ref))


@then("the operation succeeds as an already-converged no-op")
def no_op(context) -> None:
    assert context.error is None
    assert context.result.status == "no-op"
    assert not [call for call in context.native.calls if "list" not in call.argv]


@then("unrelated plugin state is unchanged")
def all_state_unchanged(context) -> None:
    assert [(item.native_ref, item.version, item.root) for item in context.native.installed] == context.snapshot


@given("the native manager exits successfully without establishing the requested state")
def false_success(context) -> None:
    configured_entry(context, "claude")
    context.native.successful_without_change = True


@when("agent-router verifies the mutation")
def verify_mutation(context) -> None:
    capture(context, lambda: context.router.install_plugin(context.ref))


@then("the operation does not report convergence")
def no_false_convergence(context) -> None:
    assert context.result.status != "installed"


@then("its outcome identifies the unverified resulting state")
def unverified_outcome(context) -> None:
    assert context.result.status == "indeterminate"
    assert not context.result.verified


@given("the native manager may have changed state before authoritative rediscovery fails")
def partial_native(context) -> None:
    configured_entry(context, "claude")
    context.native.fail_discovery_after_mutation = True


@then("the outcome reports indeterminate or partially changed state")
def partial_outcome(context) -> None:
    assert context.result.status in {"indeterminate", "partially-changed"}


@then("agent-router does not claim rollback it cannot prove")
def no_rollback_claim(context) -> None:
    assert context.native.mutation_seen
    assert context.result.status != "rolled-back"


@given("a plugin contains a registered generic artifact")
def lifecycle_artifact(context) -> None:
    context.native = FakeNativeManager(context.destination)
    context.extension = PathArtifactExtension(
        ArtifactManifest("zpp.traits", "1"), PurePath("traits/item")
    )
    context.ref = _selected_ref(Agent.CLAUDE)
    context.router = plugin_router(context, Agent.CLAUDE, extensions=(context.extension,))


@when("I install or update that plugin")
def lifecycle_with_artifact(context) -> None:
    capture(context, lambda: context.router.install_plugin(context.ref))


@then("lifecycle verification inspects only authoritative native plugin state")
def lifecycle_native_only(context) -> None:
    assert context.error is None
    assert context.result.after is not None


@then("no generic artifact is located, parsed, activated, or cached")
def artifact_not_touched(context) -> None:
    assert context.extension.contexts == []


@given("the selected agent's supported native manager is unavailable")
def unavailable_manager(context) -> None:
    configured_entry(context, "claude")
    context.native.unavailable = True


@when("I request a plugin lifecycle operation")
def request_lifecycle(context) -> None:
    capture(context, lambda: context.router.install_plugin(context.ref))


@then("the outcome reports the unavailable agent deterministically")
def unavailable_outcome(context) -> None:
    assert isinstance(context.error, PluginManagerUnavailableError)
    assert "claude" in str(context.error)


@then("no undocumented fallback mutates state")
def no_fallback(context) -> None:
    assert not context.native.installed
    assert not plugin_state_path(context.destination).exists()
