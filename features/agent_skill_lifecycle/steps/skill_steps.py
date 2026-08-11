from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from behave import given, then, when
from typer.testing import CliRunner

from agent_router import (
    Agent,
    ConflictError,
    GitIgnorePolicy,
    InvalidAssetError,
    Scope,
    Skill,
    UnsupportedAssetError,
    UnsupportedScopeError,
)
from agent_router.utils import mutation
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


@given("a managed skill modified after installation")
def given_modified_managed_skill(context) -> None:
    given_installed_skill(context)
    (context.destination / "reviewer" / "SKILL.md").write_text(
        "modified",
        encoding="utf-8",
    )


@given("a neighboring skill outside the owned target")
def given_neighboring_skill(context) -> None:
    assert (context.neighbor / "note.txt").is_file()


@given("a managed skill target removed outside agent-router")
def given_missing_managed_skill(context) -> None:
    given_installed_skill(context)
    shutil.rmtree(context.destination / "reviewer")


@given("no skill target or ownership record exists")
def given_absent_skill(context) -> None:
    context.destination = context.root / "skills"


@given("the optional agent-router command is available")
def given_command_available(context) -> None:
    context.command_runner = CliRunner()


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


@when("I force-uninstall the skill through the Python library")
def force_uninstall_skill(context) -> None:
    _capture(
        context,
        lambda: _router(context).uninstall_skill(
            "reviewer",
            destination=context.destination,
            force=True,
        ),
    )


@when("I inspect skill uninstall help")
def inspect_uninstall_help(context) -> None:
    context.command_result = context.command_runner.invoke(
        app,
        ["skill", "uninstall", "--help"],
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


@then("the exact owned skill and ownership records are removed")
def forced_skill_and_state_removed(context) -> None:
    assert context.error is None
    assert not (context.destination / "reviewer").exists()
    assert not tuple(context.home.rglob("reviewer.json"))


@then("no backup or history of the removed skill is retained")
def no_forced_removal_history(context) -> None:
    assert not tuple(context.root.rglob(".reviewer.agent-router-*"))


@then("the neighboring skill is retained")
def forced_neighbor_retained(context) -> None:
    neighboring_skills_retained(context)


@then("its stale ownership records are removed")
def stale_ownership_removed(context) -> None:
    assert not tuple(context.home.rglob("reviewer.json"))


@then("the lifecycle result reports removal")
def lifecycle_reports_removal(context) -> None:
    assert context.error is None
    assert context.result.status == "removed"


@then("the lifecycle result reports an absent no-op")
def lifecycle_reports_absent(context) -> None:
    assert context.error is None
    assert context.result.status == "absent"


@then("no destination or ownership state is created")
def absent_force_creates_nothing(context) -> None:
    assert not context.destination.exists()
    assert not tuple(context.home.rglob("reviewer.json"))


@then("no force deletion option is exposed")
def no_command_force_option(context) -> None:
    assert context.command_result.exit_code == 0
    assert "--force" not in context.command_result.stdout


@then("the request is rejected before destination mutation")
def rejected_before_mutation(context) -> None:
    assert context.error is not None
    assert not context.destination.exists()


def _init_project(context, *, git: bool = True) -> None:
    context.project_root = context.root / "project"
    context.project_root.mkdir(exist_ok=True)
    if git:
        result = subprocess.run(
            ["git", "init", "--quiet"],
            cwd=context.project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
    context.destination = context.project_root / ".agents" / "skills"


def _authoritative_source(context, *, identical: bool = False) -> None:
    context.source = _write_skill(
        context.root, "reviewer", body="old" if identical else "authoritative"
    )
    if not identical:
        (context.source / "new.txt").write_text("new", encoding="utf-8")
    context.skill = Skill.from_path(context.source)


@given("an existing repository-local skill that is {state}")
def given_existing_local_skill(context, state: str) -> None:
    _init_project(context)
    _authoritative_source(context)
    target = context.destination / "reviewer"
    if state.strip() == "modified":
        old_source = _write_skill(context.root / "old", "reviewer", body="old")
        old = Skill.from_path(old_source)
        _router(context).install_skill(
            old, scope=Scope.PROJECT, project_root=context.project_root
        )
        (target / "SKILL.md").write_text("modified", encoding="utf-8")
    else:
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("unmanaged", encoding="utf-8")
    (target / "stale.txt").write_text("stale", encoding="utf-8")
    context.target = target
    context.neighbor = context.destination / "neighbor"
    context.neighbor.mkdir()
    (context.neighbor / "keep.txt").write_text("keep", encoding="utf-8")


@given("a valid authoritative update source with different files")
def given_different_authoritative_source(context) -> None:
    assert context.skill.fingerprint


@when("I explicitly update that skill in project scope")
def update_local_skill(context) -> None:
    _capture(
        context,
        lambda: _router(context).update_skill(
            context.skill,
            scope=Scope.PROJECT,
            project_root=context.project_root,
        ),
    )


@then("the complete exact target is replaced from the update source")
def complete_target_replaced(context) -> None:
    assert context.error is None
    assert context.result.status == "updated"
    assert (context.target / "new.txt").read_text(encoding="utf-8") == "new"


@then("stale target files are removed while neighboring skills are retained")
def stale_removed_and_neighbor_retained(context) -> None:
    assert not (context.target / "stale.txt").exists()
    assert (context.neighbor / "keep.txt").read_text(encoding="utf-8") == "keep"


@then("current project ownership is recorded")
def project_ownership_recorded(context) -> None:
    records = tuple((context.project_root / ".z-agent-router").rglob("reviewer.json"))
    assert len(records) == 1
    assert not tuple(context.destination.rglob(".agent-router"))


@given("an existing repository-local skill identical to the update source")
def given_identical_local_skill(context) -> None:
    _init_project(context)
    _authoritative_source(context, identical=True)
    context.target = context.destination / "reviewer"
    context.target.mkdir(parents=True)
    for item in context.skill.files:
        path = context.target.joinpath(*item.relative_path.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(item.content)
    context.target_identity = context.target.stat().st_ino


@then("update succeeds as a no-op without rewriting the target")
def update_noop_without_rewrite(context) -> None:
    assert context.error is None
    assert context.result.status == "no-op"
    assert context.target.stat().st_ino == context.target_identity


@given("a repository-local skill target that is {state}")
def given_unsafe_local_target(context, state: str) -> None:
    _init_project(context, git=False)
    _authoritative_source(context)
    context.target = context.destination / "reviewer"
    context.destination.mkdir(parents=True)
    selected = state.strip()
    if selected == "a symbolic link":
        real = context.root / "real-target"
        real.mkdir()
        context.target.symlink_to(real, target_is_directory=True)
    elif selected == "an unsupported entry":
        context.target.write_text("not a directory", encoding="utf-8")


@then("update fails before target or router-state mutation")
def update_fails_before_mutation(context) -> None:
    assert isinstance(context.error, ConflictError)
    assert not (context.project_root / ".z-agent-router").exists()


@given("a valid authoritative update source")
def given_authoritative_source(context) -> None:
    _authoritative_source(context)


@when("I request skill update without explicit project scope and project root")
def request_user_update(context) -> None:
    _capture(context, lambda: _router(context).update_skill(context.skill, scope=Scope.USER))


@then("the request is rejected before target inspection or mutation")
def update_rejected_before_target(context) -> None:
    assert isinstance(context.error, UnsupportedScopeError)


@then("user-scope conflict protection remains unchanged")
def user_install_stays_safe(context) -> None:
    destination = context.root / "user-skills"
    target = destination / context.skill.name
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("unmanaged", encoding="utf-8")
    _capture(
        context,
        lambda: _router(context).install_skill(
            context.skill, destination=destination
        ),
    )
    assert isinstance(context.error, ConflictError)


@given("an existing repository-local skill and valid authoritative update source")
def given_update_ready_for_failure(context) -> None:
    given_existing_local_skill(context, "unmanaged")
    context.before_target = {
        item.relative_to(context.target).as_posix(): item.read_bytes()
        for item in context.target.rglob("*")
        if item.is_file()
    }


@when("target, ownership, migration, or requested Git-ignore mutation fails during update")
def fail_update_transaction(context) -> None:
    original = mutation.atomic_write

    def fail_ownership(path: Path, content: bytes) -> None:
        if ".z-agent-router" in path.parts:
            raise OSError("injected ownership failure")
        original(path, content)

    mutation.atomic_write = fail_ownership
    try:
        update_local_skill(context)
    finally:
        mutation.atomic_write = original


@then("the complete previous target and associated state are restored")
def failed_update_restored(context) -> None:
    after = {
        item.relative_to(context.target).as_posix(): item.read_bytes()
        for item in context.target.rglob("*")
        if item.is_file()
    }
    assert isinstance(context.error, OSError)
    assert after == context.before_target
    assert not (context.project_root / ".z-agent-router").exists()
    assert not (context.project_root / ".gitignore").exists()


@then("no partial or merged projection is reported as updated")
def no_partial_update(context) -> None:
    assert context.result is None


@given("a Git repository whose project state and selected skill are not ignored")
def given_unignored_project_skill(context) -> None:
    given_existing_local_skill(context, "unmanaged")


@when("I update the local skill with default ignore policy")
def update_with_default_ignore(context) -> None:
    update_local_skill(context)


@then("the repository ignores its .z-agent-router state and that exact skill target")
def exact_paths_ignored(context) -> None:
    content = (context.project_root / ".gitignore").read_text(encoding="utf-8")
    assert "/.z-agent-router/" in content
    assert "/.agents/skills/reviewer/" in content


@then("unrelated skills and ignore rules remain visible and unchanged")
def unrelated_skills_visible(context) -> None:
    content = (context.project_root / ".gitignore").read_text(encoding="utf-8")
    assert "/.agents/skills/*/" not in content
    assert context.neighbor.exists()


@given("an existing Git ignore glob effectively covers the selected skill target")
def given_existing_ignore_glob(context) -> None:
    given_existing_local_skill(context, "unmanaged")
    (context.project_root / ".gitignore").write_text(
        "/.agents/skills/*/\n", encoding="utf-8"
    )


@when("I update the local skill with exact ignore policy")
def update_with_exact_ignore(context) -> None:
    update_local_skill(context)


@then("update accepts the effective coverage without adding a redundant target rule")
def no_redundant_exact_rule(context) -> None:
    content = (context.project_root / ".gitignore").read_text(encoding="utf-8")
    assert content.count("/.agents/skills/*/") == 1
    assert "/.agents/skills/reviewer/" not in content


@given("a caller supplies a pattern that is {effect}")
def given_explicit_pattern(context, effect: str) -> None:
    given_existing_local_skill(context, "unmanaged")
    selected = effect.strip()
    if selected == "effective for the selected target":
        context.ignore_pattern = "/.agents/skills/*/"
    elif selected == "defeated by an effective negation":
        context.ignore_pattern = "!/.agents/skills/reviewer/"
    else:
        context.ignore_pattern = "*.txt"


@when("I update the local skill with pattern ignore policy")
def update_with_pattern(context) -> None:
    _capture(
        context,
        lambda: _router(context).update_skill(
            context.skill,
            scope=Scope.PROJECT,
            project_root=context.project_root,
            ignore_policy=GitIgnorePolicy("pattern", context.ignore_pattern),
        ),
    )


@then("the update {outcome} before target replacement")
def explicit_pattern_outcome(context, outcome: str) -> None:
    if outcome.strip() == "establishes that pattern":
        assert context.error is None
        assert context.ignore_pattern in (
            context.project_root / ".gitignore"
        ).read_text(encoding="utf-8")
    else:
        assert context.error is not None
        assert (context.target / "stale.txt").exists()


@given("a project directory that need not be a Git worktree")
def given_non_git_project(context) -> None:
    _init_project(context, git=False)
    _authoritative_source(context)
    context.target = context.destination / "reviewer"
    context.target.mkdir(parents=True)
    (context.target / "old.txt").write_text("old", encoding="utf-8")


@when("I update the local skill with none ignore policy")
def update_with_none(context) -> None:
    _capture(
        context,
        lambda: _router(context).update_skill(
            context.skill,
            scope=Scope.PROJECT,
            project_root=context.project_root,
            ignore_policy=GitIgnorePolicy("none"),
        ),
    )


@then("update does not inspect or change Git ignore state")
def none_bypasses_git(context) -> None:
    assert context.error is None
    assert not (context.project_root / ".gitignore").exists()


@given("a project directory outside a usable Git worktree")
def given_project_outside_git(context) -> None:
    given_non_git_project(context)


@when("I update the local skill with exact or pattern ignore policy")
def update_managed_outside_git(context) -> None:
    _capture(
        context,
        lambda: _router(context).update_skill(
            context.skill,
            scope=Scope.PROJECT,
            project_root=context.project_root,
        ),
    )


@then("update fails before changing the target, router state, or project files")
def managed_ignore_fails_before_update(context) -> None:
    assert context.error is not None
    assert (context.target / "old.txt").exists()
    assert not (context.project_root / ".z-agent-router").exists()
    assert not (context.project_root / ".gitignore").exists()
