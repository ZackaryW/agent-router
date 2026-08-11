from __future__ import annotations

import json
from pathlib import Path

from behave import given, then, when

from agent_router import (
    Agent,
    AgentEnvironment,
    ArtifactManifest,
    ArtifactPolicy,
    Scope,
    Skill,
)
from agent_router.utils import mutation
from agent_router.utils.destinations import resolve_destination
from agent_router.utils.router_state import ownership_locations, resolve_state_root
from features.support.lifecycle import capture, write_skill
from features.support.plugins import PathArtifactExtension, plugin_router, ref


def _skill_locations(context, project_root: Path | None = None):
    scope = Scope.PROJECT if project_root is not None else Scope.USER
    destination = resolve_destination(
        "codex",
        "skill",
        scope.value,
        home=context.home,
        project_root=project_root,
    )
    state_root = resolve_state_root(
        scope.value,
        home=context.home,
        project_root=project_root,
    )
    return ownership_locations(
        state_root=state_root,
        destination=destination,
        agent="codex",
        kind="skill",
        name="reviewer",
    )


@given("a valid managed asset in {scope} scope")
def given_scoped_asset(context, scope: str) -> None:
    context.scope = Scope(scope)
    context.project_root = context.root / "project" if context.scope is Scope.PROJECT else None
    if context.project_root is not None:
        context.project_root.mkdir()
    context.source = write_skill(context.root)
    context.skill = Skill.from_path(context.source)


@when("agent-router records ownership for the selected destination")
def record_scoped_ownership(context) -> None:
    from agent_router import AgentRouter

    context.router = AgentRouter(Agent.CODEX, home=context.home)
    context.result = context.router.install_skill(
        context.skill,
        scope=context.scope,
        project_root=context.project_root,
        destination=getattr(context, "custom_destination", None),
    )


@then("router state is stored beneath the {state_root} application-data root")
def scoped_state_root(context, state_root: str) -> None:
    expected = (
        context.project_root / ".z-agent-router"
        if "project" in state_root
        else context.home / ".z-agent-router"
    )
    assert tuple(expected.rglob("*.json"))


@then("no persistent router metadata is created in the native agent surface")
def no_native_metadata(context) -> None:
    assert not tuple(context.root.rglob(".agent-router"))


@given("project scope, an explicit project root, and a custom asset destination")
def given_custom_project_destination(context) -> None:
    context.scope = Scope.PROJECT
    context.project_root = context.root / "project"
    context.project_root.mkdir()
    context.custom_destination = context.root / "custom-skills"
    context.source = write_skill(context.root)
    context.skill = Skill.from_path(context.source)


@when("agent-router records ownership for the custom projection")
def record_custom_projection(context) -> None:
    record_scoped_ownership(context)


@then("the projection uses the custom destination")
def custom_projection_used(context) -> None:
    assert (context.custom_destination / "reviewer" / "SKILL.md").is_file()


@then("its metadata remains in the selected project's application-data root")
def custom_metadata_project_scoped(context) -> None:
    assert tuple((context.project_root / ".z-agent-router").rglob("reviewer.json"))
    assert not (context.custom_destination / ".agent-router").exists()


@given("an explicit isolated AgentEnvironment")
def given_isolated_environment(context) -> None:
    context.destination = context.root / "isolated-home"
    context.destination.mkdir()
    context.project_root = context.root / "isolated-project"
    context.project_root.mkdir()
    context.environment = AgentEnvironment(context.destination, context.project_root)


@when("plugin ownership and artifact policy are persisted")
def persist_isolated_plugin_state(context) -> None:
    extension = PathArtifactExtension(
        ArtifactManifest("zpp.traits", "1"), Path("traits.yaml")
    )
    context.router = plugin_router(context, Agent.CODEX, extensions=(extension,))
    context.ref = ref(Agent.CODEX)
    context.router.install_plugin(context.ref)
    context.router.set_artifact_policy(
        context.ref, "zpp.traits", ArtifactPolicy.DISABLED
    )


@then("router state uses only that environment's application-data root")
def isolated_state_root(context) -> None:
    state = context.destination / ".z-agent-router" / "plugins.json"
    assert state.is_file()
    assert not (context.home / ".z-agent-router").exists()


@then("no receipt or policy is exposed through a native plugin surface")
def no_native_plugin_metadata(context) -> None:
    assert not (context.destination / ".agent-router").exists()
    runtime_roots = [item.root for item in context.native.installed]
    assert all(not tuple(root.rglob(".z-agent-router")) for root in runtime_roots if root)


@given("two projects contain same-named managed skills for the same agent")
def given_two_same_named_projects(context) -> None:
    from agent_router import AgentRouter

    context.router = AgentRouter(Agent.CODEX, home=context.home)
    context.source = write_skill(context.root)
    context.skill = Skill.from_path(context.source)
    context.projects = (context.root / "one", context.root / "two")
    for project in context.projects:
        project.mkdir()
        context.router.install_skill(
            context.skill, scope=Scope.PROJECT, project_root=project
        )


@when("each project resolves its router ownership")
def inspect_two_projects(context) -> None:
    context.results = tuple(
        context.router.inspect_skill(
            context.skill, scope=Scope.PROJECT, project_root=project
        )
        for project in context.projects
    )


@then("each projection uses only the record bound to its canonical destination")
def records_are_project_specific(context) -> None:
    assert all(result.status == "current" for result in context.results)
    record_sets = [
        tuple((project / ".z-agent-router").rglob("reviewer.json"))
        for project in context.projects
    ]
    assert all(len(records) == 1 for records in record_sets)
    assert record_sets[0][0] != record_sets[1][0]


@then("displaced ownership evidence is rejected without mutation")
def displaced_evidence_rejected(context) -> None:
    first = tuple((context.projects[0] / ".z-agent-router").rglob("reviewer.json"))[0]
    second = tuple((context.projects[1] / ".z-agent-router").rglob("reviewer.json"))[0]
    before = second.read_bytes()
    second.write_bytes(first.read_bytes())
    result = context.router.inspect_skill(
        context.skill, scope=Scope.PROJECT, project_root=context.projects[1]
    )
    assert result.status == "conflict"
    assert second.read_bytes() == first.read_bytes()
    second.write_bytes(before)


def _prepare_legacy(context) -> None:
    from agent_router import AgentRouter

    context.router = AgentRouter(Agent.CODEX, home=context.home)
    context.source = write_skill(context.root)
    context.skill = Skill.from_path(context.source)
    context.router.install_skill(context.skill)
    context.locations = _skill_locations(context)
    context.locations.legacy.parent.mkdir(parents=True)
    context.locations.current.replace(context.locations.legacy)
    current_root = context.home / ".z-agent-router"
    for directory in sorted(current_root.rglob("*"), reverse=True):
        if directory.is_dir():
            try:
                directory.rmdir()
            except OSError:
                pass
    try:
        current_root.rmdir()
    except OSError:
        pass


@given("an intact managed projection has only a valid legacy relative ownership record")
def given_legacy_projection(context) -> None:
    _prepare_legacy(context)


@when("I inspect that projection")
def inspect_legacy_projection(context) -> None:
    context.before_legacy = context.locations.legacy.read_bytes()
    context.result = context.router.inspect_skill(context.skill)


@then("inspection reports its managed state from the legacy evidence")
def legacy_inspection_current(context) -> None:
    assert context.result.status == "current"


@then("neither legacy nor current router state is changed")
def inspection_does_not_migrate(context) -> None:
    assert context.locations.legacy.read_bytes() == context.before_legacy
    assert not context.locations.current.exists()


@when("I perform an authorized lifecycle mutation")
def mutate_legacy_projection(context) -> None:
    context.result = context.router.install_skill(context.skill)


@then("current ownership is published or consumed in the selected application-data root")
def current_state_published(context) -> None:
    assert context.locations.current.is_file()


@then("the legacy record and only proven-empty legacy router directories are removed")
def legacy_state_removed(context) -> None:
    assert not context.locations.legacy.exists()
    assert not context.locations.legacy.parent.exists()
    assert not context.locations.legacy.parent.parent.exists()


@given("current and legacy records disagree about one addressed projection")
def given_divergent_state(context) -> None:
    from agent_router import AgentRouter

    context.router = AgentRouter(Agent.CODEX, home=context.home)
    context.source = write_skill(context.root)
    context.skill = Skill.from_path(context.source)
    context.router.install_skill(context.skill)
    context.locations = _skill_locations(context)
    context.locations.legacy.parent.mkdir(parents=True)
    document = json.loads(context.locations.current.read_text(encoding="utf-8"))
    document["fingerprint"] = "0" * 64
    context.locations.legacy.write_text(json.dumps(document), encoding="utf-8")
    context.before_current = context.locations.current.read_bytes()
    context.before_legacy = context.locations.legacy.read_bytes()


@when("I inspect or mutate that projection")
def inspect_divergent_state(context) -> None:
    context.result = context.router.inspect_skill(context.skill)


@then("agent-router reports an ownership conflict")
def divergent_state_conflicts(context) -> None:
    assert context.result.status == "conflict"


@then("neither state location nor the native projection is changed")
def divergent_state_unchanged(context) -> None:
    assert context.locations.current.read_bytes() == context.before_current
    assert context.locations.legacy.read_bytes() == context.before_legacy


@given("valid legacy ownership is ready to migrate")
def given_legacy_ready(context) -> None:
    _prepare_legacy(context)
    context.before_legacy = context.locations.legacy.read_bytes()
    context.target = context.home / ".codex" / "skills" / "reviewer"
    context.before_target = {
        item.relative_to(context.target).as_posix(): item.read_bytes()
        for item in context.target.rglob("*")
        if item.is_file()
    }


@when("a later projection or state mutation fails")
def fail_legacy_migration(context) -> None:
    original = mutation.atomic_write

    def fail_current(path: Path, content: bytes) -> None:
        if ".z-agent-router" in path.parts:
            raise OSError("injected migration failure")
        original(path, content)

    mutation.atomic_write = fail_current
    try:
        capture(context, lambda: context.router.install_skill(context.skill))
    finally:
        mutation.atomic_write = original


@then("the original projection and legacy ownership evidence are restored")
def legacy_migration_restored(context) -> None:
    after = {
        item.relative_to(context.target).as_posix(): item.read_bytes()
        for item in context.target.rglob("*")
        if item.is_file()
    }
    assert isinstance(context.error, OSError)
    assert after == context.before_target
    assert context.locations.legacy.read_bytes() == context.before_legacy
    assert not context.locations.current.exists()


@then("successful migration is not reported")
def migration_not_reported(context) -> None:
    assert context.result is None
