from __future__ import annotations

import builtins
import json
import subprocess
import sys
import tomllib
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

from behave import given, then, when
from typer.testing import CliRunner

from agent_router import Agent, AgentRouter, AgentRouterError, Scope, Skill
from agent_router.cli.app import app
from features.support.lifecycle import (
    capture as _capture,
    router as _router,
    write_json_hook as _write_json_hook,
    write_kimi_hook as _write_kimi_hook,
    write_skill as _write_skill,
)


@given("a valid portable Agent Skill")
def given_portable_skill(context) -> None:
    context.source = _write_skill(context.root)
    context.skill = Skill.from_path(context.source)


def given_project_root(context) -> None:
    context.project_root = context.root / "project"
    context.project_root.mkdir(exist_ok=True)


@given("the base distribution is installed without the cli extra")
def given_base_distribution(context) -> None:
    context.base_only = True


@given("the supported distribution files")
def given_distribution_files(context) -> None:
    context.repository = Path(__file__).resolve().parents[3]


@when("I inspect the installation contract")
def inspect_installation_contract(context) -> None:
    context.readme = (context.repository / "README.md").read_text(encoding="utf-8")
    with (context.repository / "pyproject.toml").open("rb") as source:
        context.project_metadata = tomllib.load(source)


@then("base and CLI installations source agent-router from GitHub")
def github_installation_sources(context) -> None:
    source = "git+https://github.com/ZackaryW/agent-router.git"
    assert f'agent-router @ {source}' in context.readme
    assert f'agent-router[cli] @ {source}' in context.readme


@then("no package-index installation is offered")
def no_index_installation(context) -> None:
    assert "uv add agent-router\n" not in context.readme
    assert 'uv add "agent-router[cli]"' not in context.readme


@then("Git builds retain library and CLI metadata")
def git_build_metadata(context) -> None:
    metadata = context.project_metadata
    assert metadata["project"]["urls"]["Repository"] == (
        "https://github.com/ZackaryW/agent-router"
    )
    assert metadata["project"]["optional-dependencies"]["cli"]
    assert metadata["project"]["scripts"]["agent-router"]
    assert metadata["build-system"]["build-backend"]


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
    script = (
        "import builtins; original=builtins.__import__; "
        "builtins.__import__=lambda name,*a,**k: "
        '(_ for _ in ()).throw(ModuleNotFoundError("blocked typer")) '
        "if name == 'typer' else original(name,*a,**k); "
        "from agent_router import AgentRouter, Skill, Hook"
    )
    context.import_process = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )


@when("I invoke the optional command surface")
def invoke_missing_cli(context) -> None:
    from agent_router import cli

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
            [
                kind,
                "install",
                str(source),
                "--agent",
                "codex",
                "--destination",
                str(destination),
            ],
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
            [
                "hook",
                "install",
                str(source),
                "--agent",
                "codex",
                "--destination",
                str(context.root / "hooks.json"),
            ],
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
    assert any(
        status in context.cli_result.output
        for status in ("absent", "installed", "removed")
    )


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
