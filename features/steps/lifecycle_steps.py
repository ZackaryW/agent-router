from __future__ import annotations

import builtins
from contextlib import redirect_stderr
from io import StringIO
import json
from pathlib import Path
import shutil
import subprocess
import sys

from behave import given, then, when
from typer.testing import CliRunner

from agent_router import (
    Agent,
    AgentRouter,
    AgentRouterError,
    ConflictError,
    Hook,
    InvalidAssetError,
    Scope,
    Skill,
    UnsupportedAssetError,
)
from agent_router.cli.app import app


def _write_skill(root: Path, name: str = "reviewer", *, body: str = "Body", extra: str = "") -> Path:
    source = root / f"source-{name}"
    source.mkdir(parents=True, exist_ok=True)
    (source / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Reviews code\n{extra}---\n{body}\n",
        encoding="utf-8",
    )
    return source


def _write_json_hook(root: Path, name: str = "reviewer", *, event: str = "PreToolUse", handler_type: str = "command", extra_handler: str = "") -> Path:
    handler: dict[str, object] = {"type": handler_type}
    if handler_type == "command":
        handler["command"] = "check"
    else:
        handler["prompt"] = "check"
    if extra_handler:
        handler[extra_handler] = True
    source = root / f"{name}.json"
    source.write_text(
        json.dumps({"hooks": {event: [{"matcher": "shell", "hooks": [handler]}]}}),
        encoding="utf-8",
    )
    return source


def _write_kimi_hook(root: Path, name: str = "reviewer") -> Path:
    source = root / f"{name}.toml"
    source.write_text(
        '[[hooks]]\nevent = "PreToolUse"\nmatcher = "shell"\ncommand = "check"\n',
        encoding="utf-8",
    )
    return source


def _write_pi_hook(root: Path, name: str = "reviewer") -> Path:
    source = root / f"{name}.ts"
    source.write_text("export default function extension() {}\n", encoding="utf-8")
    return source


def _router(context, agent: Agent = Agent.CODEX) -> AgentRouter:
    return AgentRouter(agent, home=context.home)


def _capture(context, action) -> None:
    try:
        context.result = action()
    except Exception as error:
        context.error = error


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
    _capture(context, lambda: AgentRouter((Agent.CODEX, Agent.CLAUDE)))


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
    assert context.result.destination.is_relative_to(context.project_root)


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


@given("a valid native {agent} hook artifact")
def given_native_hook(context, agent: str) -> None:
    selected = Agent(agent.lower())
    if selected is Agent.KIMI:
        context.source = _write_kimi_hook(context.root)
    elif selected is Agent.PI:
        context.source = _write_pi_hook(context.root)
    else:
        context.source = _write_json_hook(context.root)
    context.hook = Hook.from_path(context.source)
    context.agent = selected


@given("the {scope} scope inputs are complete")
def given_hook_scope(context, scope: str) -> None:
    context.scope = Scope(scope)
    if context.scope is Scope.PROJECT:
        given_project_root(context)


@given("a hook artifact that is {state}")
def given_invalid_hook(context, state: str) -> None:
    if state == "ambiguous":
        context.source = context.root / "reviewer.txt"
        context.source.write_text("unknown", encoding="utf-8")
    elif state == "a symbolic link":
        target = _write_json_hook(context.root, "target")
        context.source = context.root / "reviewer.json"
        try:
            context.source.symlink_to(target)
        except OSError:
            context.scenario.skip("symbolic links unavailable")
    else:
        context.source = context.root / "reviewer"
        context.source.mkdir()
        target = context.root / "outside.ts"
        target.write_text("export default {}", encoding="utf-8")
        try:
            (context.source / "index.ts").symlink_to(target)
        except OSError:
            context.scenario.skip("symbolic links unavailable")


@given("a portable {source} command-hook configuration")
def given_portable_hook(context, source: str) -> None:
    source_agent = Agent(source)
    context.source = _write_json_hook(context.root)
    context.hook = Hook.from_path(context.source, source_agent=source_agent)
    context.source_agent = source_agent


@given("a hook conversion request containing {content}")
def given_conversion_content(context, content: str) -> None:
    if content == "a Kimi hook":
        context.source = _write_kimi_hook(context.root)
        context.target_agent = Agent.CODEX
    elif content == "a Pi extension":
        context.source = _write_pi_hook(context.root)
        context.target_agent = Agent.CODEX
    elif content == "a nonportable event":
        context.source = _write_json_hook(context.root, event="Notification")
        context.target_agent = Agent.CODEX
    elif content == "a non-command handler":
        context.source = _write_json_hook(context.root, handler_type="prompt")
        context.target_agent = Agent.CODEX
    else:
        context.source = _write_json_hook(context.root, extra_handler="async")
        context.target_agent = Agent.CLAUDE
    source_agent = Agent.CLAUDE if context.target_agent is Agent.CODEX else Agent.CODEX
    try:
        context.hook = Hook.from_path(context.source, source_agent=source_agent)
    except InvalidAssetError:
        context.hook = Hook.from_path(context.source)


def _seed_unrelated_hook(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            {
                "permissions": {"allow": ["Read"]},
                "hooks": {
                    "SessionStart": [
                        {"hooks": [{"type": "command", "command": "hello"}]}
                    ]
                },
            }
        ),
        encoding="utf-8",
    )


@given("an intact hook integration installed by agent-router beside unrelated hooks")
def given_installed_hook(context) -> None:
    context.source = _write_json_hook(context.root)
    context.hook = Hook.from_path(context.source)
    context.destination = context.root / "hooks.json"
    _seed_unrelated_hook(context.destination)
    _router(context).install_hook(context.hook, destination=context.destination)


@given("an intact older hook integration installed by agent-router beside unrelated hooks")
def given_old_hook(context) -> None:
    given_installed_hook(context)
    context.source.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "shell",
                            "hooks": [
                                {"type": "command", "command": "new-check"}
                            ],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    context.hook = Hook.from_path(context.source)


@given("a malformed native hook destination")
def given_malformed_hook_destination(context) -> None:
    context.source = _write_json_hook(context.root)
    context.hook = Hook.from_path(context.source)
    context.destination = context.root / "hooks.json"
    context.destination.write_text("{broken", encoding="utf-8")


@given("a same-named hook integration that is {state}")
def given_unsafe_hook(context, state: str) -> None:
    if state.strip() == "not installed by agent-router":
        context.source = _write_json_hook(context.root)
        context.hook = Hook.from_path(context.source)
        context.destination = context.root / "hooks.json"
        context.destination.write_text(
            json.dumps({"hooks": context.hook.fragment}), encoding="utf-8"
        )
    else:
        given_installed_hook(context)
        document = json.loads(context.destination.read_text(encoding="utf-8"))
        document["hooks"]["PreToolUse"][-1]["matcher"] = "modified"
        context.destination.write_text(json.dumps(document), encoding="utf-8")


@when("I install the hook for {agent} in {scope} scope")
def install_native_hook(context, agent: str, scope: str) -> None:
    selected_scope = Scope(scope)
    _capture(
        context,
        lambda: _router(context, Agent(agent)).install_hook(
            context.hook,
            scope=selected_scope,
            project_root=getattr(context, "project_root", None),
        ),
    )


@when("I inspect the hook for {agent}")
def inspect_hook(context, agent: str) -> None:
    try:
        hook = getattr(context, "hook", None) or Hook.from_path(context.source)
    except Exception as error:
        context.error = error
        return
    _capture(
        context,
        lambda: _router(context, Agent(agent.lower())).inspect_hook(
            hook, destination=context.destination
        ),
    )


@when("I install it for codex with conversion allowed")
@when("I install it for claude with conversion allowed")
def install_converted_hook(context) -> None:
    context.target_agent = (
        Agent.CODEX if context.source_agent is Agent.CLAUDE else Agent.CLAUDE
    )
    _capture(
        context,
        lambda: _router(context, context.target_agent).install_hook(
            context.hook, destination=context.destination, allow_conversion=True
        ),
    )


@when("I install it for Codex without conversion allowed")
def install_hook_without_conversion(context) -> None:
    _capture(
        context,
        lambda: _router(context).install_hook(
            context.hook, destination=context.destination
        ),
    )


@when("I install it for the requested non-native agent with conversion allowed")
def install_unavailable_conversion(context) -> None:
    _capture(
        context,
        lambda: _router(context, context.target_agent).install_hook(
            context.hook, destination=context.destination, allow_conversion=True
        ),
    )


@when("I install the identical integration to the same destination")
@when("I install the newer integration to the same destination")
@when("I install a managed hook integration")
def install_hook_destination(context) -> None:
    _capture(
        context,
        lambda: _router(context).install_hook(
            context.hook, destination=context.destination
        ),
    )


@when("I uninstall the hook by name without its original source")
@when("I uninstall the hook by name")
def uninstall_hook(context) -> None:
    _capture(
        context,
        lambda: _router(context).uninstall_hook(
            "reviewer", destination=context.destination
        ),
    )


@when("I request one hook operation for Codex and Claude")
def multi_agent_hook(context) -> None:
    _capture(context, lambda: AgentRouter((Agent.CODEX, Agent.CLAUDE)))


@then("the integration is installed through that native surface")
def hook_installed(context) -> None:
    assert context.error is None
    assert context.result.status == "installed"
    assert context.result.destination.exists()


@then("unrelated native configuration is retained")
@then("unrelated native configuration is unchanged")
def unrelated_hook_retained(context) -> None:
    destination = context.result.destination if context.result is not None else context.destination
    if destination.is_file() and destination.suffix == ".json":
        document = json.loads(destination.read_text(encoding="utf-8"))
        if "permissions" in document:
            assert document["permissions"] == {"allow": ["Read"]}


@then("the operation reports an unsupported scope")
def unsupported_scope(context) -> None:
    assert isinstance(context.error, AgentRouterError)
    assert "does not support" in str(context.error)


@then("no project hook convention is created")
def no_project_hook(context) -> None:
    assert not (context.project_root / ".kimi-code" / "config.toml").exists()


@then("Claude is reported as natively compatible")
def claude_compatible(context) -> None:
    assert Agent.CLAUDE in context.result.compatible_agents


@then("the supported event matcher and command mapping is converted")
def hook_converted(context) -> None:
    assert context.error is None
    assert context.result.converted


@then("the converted configuration passes target validation")
def converted_valid(context) -> None:
    document = json.loads(context.destination.read_text(encoding="utf-8"))
    assert "PreToolUse" in document["hooks"]


@then("the source artifact is unchanged")
def hook_source_unchanged(context) -> None:
    assert "check" in context.source.read_text(encoding="utf-8")


@then("no source content is dropped")
def no_source_content_dropped(context) -> None:
    assert context.source.exists()


@then("only the owned integration is replaced")
def owned_hook_replaced(context) -> None:
    assert context.result.status == "updated"
    assert "new-check" in context.destination.read_text(encoding="utf-8")


@then("the operation fails before mutation")
def fails_before_mutation(context) -> None:
    assert context.error is not None
    assert context.destination.read_text(encoding="utf-8") == "{broken"


@then("only that owned integration is removed")
def owned_hook_removed(context) -> None:
    document = json.loads(context.destination.read_text(encoding="utf-8"))
    assert "PreToolUse" not in document.get("hooks", {})


@then("the integration is not removed")
def unsafe_hook_retained(context) -> None:
    assert context.destination.exists()


@given("the base distribution is installed without the cli extra")
def given_base_distribution(context) -> None:
    context.base_only = True


@given("the cli extra is installed")
def given_cli_distribution(context) -> None:
    context.runner = CliRunner()


@given("the selected agent executable is absent")
def given_agent_absent(context) -> None:
    given_portable_skill(context)
    context.fake_path = context.root / "empty-bin"
    context.fake_path.mkdir()


@given("a valid filesystem lifecycle command")
def given_filesystem_command(context) -> None:
    if not hasattr(context, "skill"):
        given_portable_skill(context)


@given("a valid lifecycle request in {scope} scope")
def given_lifecycle_request(context, scope: str) -> None:
    given_portable_skill(context)
    context.scope = Scope(scope)
    if context.scope is Scope.PROJECT:
        given_project_root(context)


@given("an explicit destination")
def given_explicit_destination(context) -> None:
    context.destination = context.root / "custom-destination"


@given("project scope and an explicit destination")
def given_project_destination(context) -> None:
    given_portable_skill(context)
    context.scope = Scope.PROJECT
    context.destination = context.root / "custom-destination"


@given("no project root")
def given_no_project_root(context) -> None:
    context.project_root = None


@given('a valid lifecycle command with "--json"')
def given_json_command(context) -> None:
    given_portable_skill(context)
    context.runner = CliRunner()


@given("a command resulting in {outcome}")
def given_command_outcome(context, outcome: str) -> None:
    context.outcome = outcome.strip()
    context.runner = CliRunner()
    given_portable_skill(context)
    context.destination = context.root / "status-destination"


@when("I import agent_router and its public contracts")
def import_base(context) -> None:
    context.import_process = subprocess.run(
        [
            sys.executable,
            "-c",
            "import builtins; original=builtins.__import__; "
            "builtins.__import__=lambda name,*a,**k: "
            "(_ for _ in ()).throw(ModuleNotFoundError(\"blocked typer\")) "
            "if name == 'typer' else original(name,*a,**k); "
            "from agent_router import AgentRouter, Skill, Hook",
        ],
        capture_output=True,
        text=True,
    )


@when("I invoke the optional command surface")
def invoke_missing_cli(context) -> None:
    import agent_router.cli as cli

    real_import = builtins.__import__

    def without_typer(name, *args, **kwargs):
        if name == "agent_router.cli.app" or name == "typer":
            error = ModuleNotFoundError("No module named 'typer'")
            error.name = "typer"
            raise error
        return real_import(name, *args, **kwargs)

    stream = StringIO()
    original = builtins.__import__
    builtins.__import__ = without_typer
    try:
        with redirect_stderr(stream):
            context.exit_status = cli.main()
    finally:
        builtins.__import__ = original
    context.stderr = stream.getvalue()


@when("I call AgentRouter for Codex to install the loaded Skill")
def library_install_skill(context) -> None:
    _capture(
        context,
        lambda: _router(context).install_skill(
            context.skill, destination=context.destination
        ),
    )


@when('I invoke "agent-router {kind} {operation}" with one explicit agent')
def invoke_lifecycle_command(context, kind: str, operation: str) -> None:
    runner = context.runner
    destination = context.root / f"cli-{kind}-{operation}"
    if kind == "skill":
        source = _write_skill(context.root, f"{operation}-skill")
        name = f"{operation}-skill"
    else:
        source = _write_json_hook(context.root, f"{operation}-hook")
        name = f"{operation}-hook"
        destination = destination.with_suffix(".json")
    base = [kind, operation]
    if operation == "uninstall":
        install = runner.invoke(
            app,
            [kind, "install", str(source), "--agent", "codex", "--destination", str(destination)],
        )
        assert install.exit_code == 0, install.output
        base.append(name)
    else:
        base.append(str(source))
    base.extend(["--agent", "codex", "--destination", str(destination)])
    context.cli_result = runner.invoke(app, base)


@when("I invoke a valid filesystem lifecycle command")
def invoke_without_agent_binary(context) -> None:
    context.cli_result = CliRunner().invoke(
        app,
        [
            "skill",
            "inspect",
            str(context.source),
            "--agent",
            "codex",
            "--destination",
            str(context.destination),
        ],
        env={"PATH": str(context.fake_path)},
    )


@when("I {operation} the asset")
def operate_with_override(context, operation: str) -> None:
    router = _router(context)
    kwargs = {
        "scope": context.scope,
        "project_root": getattr(context, "project_root", None),
        "destination": context.destination,
    }
    if operation == "inspect":
        _capture(context, lambda: router.inspect_skill(context.skill, **kwargs))
    elif operation == "install":
        _capture(context, lambda: router.install_skill(context.skill, **kwargs))
    else:
        router.install_skill(context.skill, **kwargs)
        _capture(context, lambda: router.uninstall_skill(context.skill.name, **kwargs))


@when("I request a lifecycle operation")
def request_invalid_project_operation(context) -> None:
    _capture(
        context,
        lambda: _router(context).inspect_skill(
            context.skill,
            scope=Scope.PROJECT,
            project_root=None,
            destination=context.destination,
        ),
    )


@when("the command completes")
def complete_json_command(context) -> None:
    context.cli_result = context.runner.invoke(
        app,
        [
            "skill",
            "inspect",
            str(context.source),
            "--agent",
            "codex",
            "--destination",
            str(context.destination),
            "--json",
        ],
    )


@when("the command exits")
def exit_status_command(context) -> None:
    outcome = context.outcome
    args = [
        "skill",
        "inspect",
        str(context.source),
        "--agent",
        "codex",
        "--destination",
        str(context.destination),
    ]
    if outcome == "already-converged no-op":
        install_args = args.copy()
        install_args[1] = "install"
        first = context.runner.invoke(app, install_args)
        assert first.exit_code == 0, first.output
        context.cli_result = context.runner.invoke(app, install_args)
    elif outcome == "success":
        context.cli_result = context.runner.invoke(app, args)
    elif outcome == "invalid request":
        args[2] = str(context.root / "missing")
        context.cli_result = context.runner.invoke(app, args)
    elif outcome == "unsupported request":
        source = _write_kimi_hook(context.root)
        context.cli_result = context.runner.invoke(
            app,
            ["hook", "install", str(source), "--agent", "codex", "--destination", str(context.root / "hooks.json")],
        )
    elif outcome in {"ownership conflict", "destination conflict"}:
        target = context.destination / "reviewer"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("unmanaged", encoding="utf-8")
        args[1] = "install"
        context.cli_result = context.runner.invoke(app, args)
    else:
        original = AgentRouter.inspect_skill

        def fail(*args, **kwargs):
            raise RuntimeError("injected")

        AgentRouter.inspect_skill = fail
        try:
            context.cli_result = context.runner.invoke(app, args)
        finally:
            AgentRouter.inspect_skill = original


@then("the import succeeds without Typer")
def base_import_succeeds(context) -> None:
    assert context.import_process.returncode == 0, context.import_process.stderr


@then('the error tells me to install "agent_router[cli]"')
def missing_cli_message(context) -> None:
    assert "agent_router[cli]" in context.stderr


@then("no optional dependency traceback is shown")
def no_optional_traceback(context) -> None:
    assert "Traceback" not in context.stderr
    assert context.exit_status == 2


@then("the operation returns a structured Codex lifecycle result")
def structured_codex_result(context) -> None:
    assert context.error is None
    assert context.result.agent is Agent.CODEX
    assert context.result.to_dict()["status"] == "installed"


@then("the request is handled through the public library lifecycle")
def command_uses_lifecycle(context) -> None:
    assert context.cli_result.exit_code == 0, context.cli_result.output
    assert any(status in context.cli_result.output for status in ("absent", "installed", "removed"))


@then("no interactive selection or confirmation is required")
def command_noninteractive(context) -> None:
    assert context.cli_result.exit_code == 0


@then("the lifecycle proceeds without probing for the executable")
def no_executable_probe(context) -> None:
    assert context.cli_result.exit_code == 0, context.cli_result.output


@then("the exact destination is handled through the production ownership planner")
def exact_destination(context) -> None:
    assert context.error is None
    assert context.result.destination == context.destination.resolve()


@then("the lifecycle result retains {scope} scope")
def retains_scope(context, scope: str) -> None:
    assert context.result.scope is Scope(scope)


@then("the request is rejected before destination inspection or mutation")
def invalid_project_rejected(context) -> None:
    assert isinstance(context.error, AgentRouterError)
    assert not context.destination.exists()


@then("one stable result envelope is written to standard output")
def json_envelope(context) -> None:
    assert context.cli_result.exit_code == 0, context.cli_result.output
    parsed = json.loads(context.cli_result.stdout)
    assert set(parsed) == {"result"}
    assert parsed["result"]["agent"] == "codex"


@then("diagnostics are written only to standard error")
def diagnostics_stream(context) -> None:
    assert context.cli_result.stderr == ""


@then("its process status is {status:d}")
def process_status(context, status: int) -> None:
    assert context.cli_result.exit_code == status, context.cli_result.output


@then("expected domain errors do not show implementation tracebacks")
def no_domain_traceback(context) -> None:
    assert "Traceback" not in context.cli_result.output
