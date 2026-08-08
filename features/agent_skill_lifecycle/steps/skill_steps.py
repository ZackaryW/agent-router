from __future__ import annotations

from behave import given, then, when
from typer.testing import CliRunner

from agent_router import (
    Agent,
    ConflictError,
    InvalidAssetError,
    Scope,
    Skill,
    UnsupportedAssetError,
)
from agent_router.cli.app import app
from features.support.lifecycle import (
    capture as _capture,
    router as _router,
    write_skill as _write_skill,
)

@given("a valid portable Agent Skill")
def given_portable_skill(context) -> None:
    context.source = _write_skill(context.root)
    context.skill = Skill.from_path(context.source)


@given('a valid portable Agent Skill named "{name}"')
def given_named_skill(context, name: str) -> None:
    context.source = _write_skill(context.root, name)
    context.skill = Skill.from_path(context.source)


@given("an explicit project root")
def given_project_root(context) -> None:
    context.project_root = context.root / "project"
    context.project_root.mkdir(exist_ok=True)


@given("a valid skill that is not compatible with Codex")
def given_claude_skill(context) -> None:
    context.source = _write_skill(context.root, extra="hooks: {}\n")
    context.skill = Skill.from_path(context.source)


@given("a skill containing a symbolic link")
def given_symlink_skill(context) -> None:
    context.source = _write_skill(context.root)
    target = context.root / "outside.txt"
    target.write_text("outside", encoding="utf-8")
    try:
        (context.source / "linked.txt").symlink_to(target)
    except OSError:
        context.scenario.skip("symbolic links unavailable")


@given("an intact skill projection installed by agent-router")
def given_installed_skill(context) -> None:
    given_named_skill(context, "reviewer")
    context.destination = context.root / "skills"
    _router(context).install_skill(context.skill, destination=context.destination)
    context.neighbor = context.destination / "neighbor"
    context.neighbor.mkdir(parents=True)
    (context.neighbor / "note.txt").write_text("keep", encoding="utf-8")


@given("an intact older skill projection installed by agent-router")
def given_old_skill(context) -> None:
    given_installed_skill(context)
    (context.source / "SKILL.md").write_text(
        "---\nname: reviewer\ndescription: Reviews code\n---\nNew body\n",
        encoding="utf-8",
    )
    context.skill = Skill.from_path(context.source)


@given("a same-named skill not installed by agent-router")
def given_unmanaged_skill(context) -> None:
    given_named_skill(context, "reviewer")
    context.destination = context.root / "skills"
    target = context.destination / "reviewer"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("unmanaged", encoding="utf-8")


@given("a same-named skill that is {state}")
def given_unsafe_skill(context, state: str) -> None:
    if state.strip() == "not installed by agent-router":
        given_unmanaged_skill(context)
    else:
        given_installed_skill(context)
        (context.destination / "reviewer" / "SKILL.md").write_text(
            "modified", encoding="utf-8"
        )


@when("I inspect the skill for {agent}")
def inspect_skill(context, agent: str) -> None:
    selected = Agent(agent.lower())
    if not hasattr(context, "skill"):
        _capture(context, lambda: Skill.from_path(context.source))
        return
    _capture(
        context,
        lambda: _router(context, selected).inspect_skill(
            context.skill, destination=context.destination
        ),
    )


@when("I install the skill for Codex without selecting a scope")
def install_default_codex_skill(context) -> None:
    _capture(context, lambda: _router(context).install_skill(context.skill))


@when("I install the skill for {agent} in project scope")
def install_project_skill(context, agent: str) -> None:
    _capture(
        context,
        lambda: _router(context, Agent(agent)).install_skill(
            context.skill, scope=Scope.PROJECT, project_root=context.project_root
        ),
    )


@when("I install the skill for Codex with conversion allowed")
def install_incompatible_skill(context) -> None:
    _capture(
        context,
        lambda: _router(context).install_skill(
            context.skill, destination=context.destination, allow_conversion=True
        ),
    )


@when("I install the identical skill to the same destination")
@when("I install the newer skill to the same destination")
@when("I install a managed skill to that destination")
def install_skill_to_destination(context) -> None:
    _capture(
        context,
        lambda: _router(context).install_skill(
            context.skill, destination=context.destination
        ),
    )


@when("I uninstall the skill by name without its original source")
@when("I uninstall the skill by name")
def uninstall_skill(context) -> None:
    _capture(
        context,
        lambda: _router(context).uninstall_skill(
            "reviewer", destination=context.destination
        ),
    )


@when("I request one skill operation for Codex and Claude")
def multi_agent_skill(context) -> None:
    result = CliRunner().invoke(
        app,
        [
            "skill",
            "inspect",
            str(context.source),
            "--agent",
            "codex",
            "--agent",
            "claude",
            "--destination",
            str(context.destination),
        ],
    )
    context.error = ValueError(result.output) if result.exit_code != 0 else None


@then("the skill is reported as natively compatible")
def skill_compatible(context) -> None:
    assert context.error is None
    assert context.result.agent in context.result.compatible_agents


@then("no destination is changed")
def no_destination_change(context) -> None:
    assert not context.destination.exists()


@then('the owned skill is installed beneath "~/.codex/skills"')
def codex_default_path(context) -> None:
    assert (context.home / ".codex" / "skills" / "reviewer" / "SKILL.md").is_file()


@then("the lifecycle result reports user scope")
def result_user_scope(context) -> None:
    assert context.result.scope is Scope.USER


@then("the owned skill is installed through the agent's native project skill surface")
def native_project_skill(context) -> None:
    assert context.error is None
    assert context.result.destination.is_relative_to(context.project_root.resolve())


@then("the operation reports an unsupported asset")
def reports_unsupported_asset(context) -> None:
    assert isinstance(context.error, UnsupportedAssetError) or (
        context.result is not None and context.result.status == "unsupported"
    )


@then("neither the source nor destination is changed")
def source_destination_unchanged(context) -> None:
    assert context.source.exists()
    assert not context.destination.exists()


@then("the operation reports invalid source content")
def reports_invalid_source(context) -> None:
    assert isinstance(context.error, InvalidAssetError)


@then("the symbolic link is not followed")
def symlink_not_followed(context) -> None:
    assert isinstance(context.error, InvalidAssetError)


@then("installation succeeds as a no-op")
def install_noop(context) -> None:
    assert context.error is None
    assert context.result.status == "no-op"


@then("unrelated destination content is unchanged")
def destination_unrelated_unchanged(context) -> None:
    assert (context.neighbor / "note.txt").read_text(encoding="utf-8") == "keep"


@then("only the owned skill projection is replaced")
def owned_skill_replaced(context) -> None:
    assert context.result.status == "updated"
    assert "New body" in (context.destination / "reviewer" / "SKILL.md").read_text(
        encoding="utf-8"
    )


@then("the operation reports a conflict")
@then("the operation reports an ownership conflict")
def reports_conflict(context) -> None:
    assert isinstance(context.error, ConflictError)


@then("the existing skill is unchanged")
@then("the skill is not removed")
def skill_unchanged(context) -> None:
    assert (context.destination / "reviewer" / "SKILL.md").exists()


@then("only that owned skill projection is removed")
def owned_skill_removed(context) -> None:
    assert not (context.destination / "reviewer").exists()


@then("neighboring skills are retained")
def neighboring_skills_retained(context) -> None:
    assert context.neighbor.exists()


@then("the request is rejected before destination mutation")
def rejected_before_mutation(context) -> None:
    assert context.error is not None
    assert not context.destination.exists()
