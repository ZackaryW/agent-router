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

from agent_router import (
    Agent,
    AgentEnvironment,
    AgentRouter,
    AgentRouterError,
    ArtifactEffectiveState,
    ArtifactManifest,
    ArtifactPolicy,
    PluginRef,
    Scope,
    Skill,
)
from agent_router.cli.app import app
import agent_router.cli.plugins as plugin_cli
from features.support.lifecycle import (
    capture as _capture,
    router as _router,
    write_json_hook as _write_json_hook,
    write_kimi_hook as _write_kimi_hook,
    write_skill as _write_skill,
)
from features.support.plugins import (
    FakeNativeManager,
    PathArtifactExtension,
    plugin_router,
    ref as plugin_ref,
)
from pathlib import PurePath


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


@then("project metadata supports Python 3.11 and later")
def python_311_metadata(context) -> None:
    assert context.project_metadata["project"]["requires-python"] == ">=3.11"


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


def _invoke_lifecycle_command(context, kind: str, operation: str) -> None:
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


@when('I invoke "agent-router skill {operation}" with one explicit agent')
def invoke_skill_lifecycle_command(context, operation: str) -> None:
    _invoke_lifecycle_command(context, "skill", operation)


@when('I invoke "agent-router hook {operation}" with one explicit agent')
def invoke_hook_lifecycle_command(context, operation: str) -> None:
    _invoke_lifecycle_command(context, "hook", operation)


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
@then("the request is handled through the public agent-bound library")
def command_uses_lifecycle(context) -> None:
    assert context.cli_result.exit_code == 0, context.cli_result.output
    assert any(
        status in context.cli_result.output
        for status in (
            "absent",
            "installed",
            "updated",
            "removed",
            "no-op",
            "active",
            "inactive",
            "plugin record",
        )
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


@when("I construct an agent-bound router with an AgentEnvironment and an artifact extension")
def construct_plugin_library_without_cli(context) -> None:
    script = """
import builtins
from pathlib import Path, PurePath
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name == 'typer':
        raise ModuleNotFoundError('blocked typer')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from agent_router import Agent, AgentEnvironment, AgentRouter, ArtifactManifest, ArtifactPolicy, PluginRef
class Extension:
    manifest = ArtifactManifest('zpp.traits', '1')
    def locate(self, context): return (PurePath('traits'),)
environment = AgentEnvironment(Path.cwd())
router = AgentRouter(Agent.CODEX, environment=environment, extensions=(Extension(),))
ref = PluginRef(Agent.CODEX, 'review@configured', 'user', 'configured')
assert ArtifactPolicy.INHERIT.value == 'inherit'
"""
    context.import_process = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )


@then("PluginRef, ArtifactManifest, policy, status, discovery, resolution, and lifecycle contracts are available")
def plugin_contracts_available(context) -> None:
    assert context.import_process.returncode == 0, context.import_process.stderr


@then("Typer is not imported")
def typer_not_imported(context) -> None:
    assert context.import_process.returncode == 0, context.import_process.stderr


def _invoke_plugin_cli(context, args: list[str], *, artifact: bool = False) -> None:
    context.native = getattr(context, "native", FakeNativeManager(context.destination))
    extensions = ()
    if artifact:
        plugin = context.native.installed[0] if context.native.installed else context.native.add()
        path = plugin.root / "traits" / "item"
        path.parent.mkdir(exist_ok=True)
        path.write_text("item", encoding="utf-8")
        extensions = (
            PathArtifactExtension(
                ArtifactManifest("zpp.traits", "1"), PurePath("traits/item")
            ),
        )

    def factory(agent, **kwargs):
        del kwargs
        return AgentRouter(
            agent,
            environment=AgentEnvironment(context.destination),
            extensions=extensions,
            process_runner=context.native,
        )

    original = plugin_cli.AgentRouter
    plugin_cli.AgentRouter = factory
    try:
        context.cli_result = context.runner.invoke(app, args)
    finally:
        plugin_cli.AgentRouter = original


@when('I invoke "agent-router plugin {operation}" with one explicit agent')
def invoke_plugin_command(context, operation: str) -> None:
    context.destination = context.root / f"plugin-{operation.replace(' ', '-')}"
    context.native = FakeNativeManager(context.destination)
    selected = plugin_ref(Agent.CLAUDE)
    base = ["plugin"]
    artifact = operation.startswith("artifact ")
    if operation == "discover":
        args = base + ["discover"]
    elif operation == "install":
        args = base + ["install", selected.native_ref]
    elif operation in {"update", "remove"}:
        setup = plugin_router(context, Agent.CLAUDE)
        setup.install_plugin(selected)
        context.native.calls.clear()
        args = base + [operation, selected.native_ref]
    elif operation == "artifact status":
        context.native.add()
        args = base + ["artifact", "status", selected.native_ref, "zpp.traits"]
    else:
        context.native.add()
        args = base + [
            "artifact",
            "set",
            selected.native_ref,
            "zpp.traits",
            "disabled",
        ]
    args.extend(
        ["--agent", "claude", "--destination", str(context.destination)]
    )
    _invoke_plugin_cli(context, args, artifact=artifact)


@then("no interactive agent selection is required")
def no_agent_selection(context) -> None:
    assert context.cli_result.exit_code == 0, context.cli_result.output


@when('I invoke plugin discovery with and without "--available"')
def invoke_plugin_discovery_modes(context) -> None:
    context.destination = context.root / "plugin-discovery"
    context.native = FakeNativeManager(context.destination)
    context.native.add()
    available = context.native.add("available@configured")
    context.native.installed.remove(available)
    context.native.available.append(available)
    common = [
        "plugin",
        "discover",
        "--agent",
        "claude",
        "--destination",
        str(context.destination),
        "--json",
    ]
    _invoke_plugin_cli(context, common)
    context.default_discovery = json.loads(context.cli_result.stdout)["result"]
    _invoke_plugin_cli(context, common + ["--available"])
    context.available_discovery = json.loads(context.cli_result.stdout)["result"]


@then("the default result contains installed plugins only")
def default_installed_only(context) -> None:
    assert context.default_discovery
    assert all(item["installed"] for item in context.default_discovery)


@then("the explicit result may include configured native catalog entries")
def available_included(context) -> None:
    assert any(not item["installed"] for item in context.available_discovery)


@given("a scoped PluginRef and a registered artifact identifier")
def scoped_artifact_ref(context) -> None:
    context.destination = context.root / "artifact-policy"
    context.native = FakeNativeManager(context.destination)
    plugin = context.native.add(scope="project")
    artifact = plugin.root / "traits" / "item"
    artifact.parent.mkdir()
    artifact.write_text("item", encoding="utf-8")
    context.extension = PathArtifactExtension(
        ArtifactManifest("zpp.traits", "1"), PurePath("traits/item")
    )
    context.plugin_ref = plugin_ref(Agent.CLAUDE, scope="project")
    context.plugin_router = plugin_router(
        context, Agent.CLAUDE, extensions=(context.extension,)
    )


@when("I query status and set inherit, enabled, or disabled through the library or CLI")
def query_and_set_policies(context) -> None:
    context.statuses = [
        context.plugin_router.artifact_status(context.plugin_ref, "zpp.traits")
    ]
    for policy in (
        ArtifactPolicy.ENABLED,
        ArtifactPolicy.DISABLED,
        ArtifactPolicy.INHERIT,
    ):
        context.statuses.append(
            context.plugin_router.set_artifact_policy(
                context.plugin_ref, "zpp.traits", policy
            )
        )


@then("the result reports requested policy, effective status, reason, and canonical absolute paths")
def complete_artifact_status(context) -> None:
    assert {status.policy for status in context.statuses} >= {
        ArtifactPolicy.INHERIT,
        ArtifactPolicy.ENABLED,
        ArtifactPolicy.DISABLED,
    }
    assert all(status.reason for status in context.statuses)
    assert context.statuses[0].effective is ArtifactEffectiveState.ACTIVE
    assert context.statuses[0].paths[0].is_absolute()


@then("native plugin enablement is unchanged")
def native_enablement_unchanged(context) -> None:
    assert context.native.installed[0].enabled


@given("an explicit plugin destination and equivalent AgentEnvironment")
def explicit_plugin_environment(context) -> None:
    context.default_sentinel = context.home / "plugins" / "sentinel"
    context.default_sentinel.parent.mkdir(parents=True)
    context.default_sentinel.write_text("unchanged", encoding="utf-8")
    context.destination = context.root / "isolated-agent"
    context.native = FakeNativeManager(context.destination)
    context.environment = AgentEnvironment(context.destination)
    context.extension = PathArtifactExtension(
        ArtifactManifest("zpp.traits", "1"), PurePath("traits/item")
    )
    context.plugin_router = AgentRouter(
        Agent.CLAUDE,
        environment=context.environment,
        extensions=(context.extension,),
        process_runner=context.native,
    )
    context.plugin_ref = plugin_ref(Agent.CLAUDE)


@when("I discover, mutate, or resolve artifacts for the selected agent")
def use_isolated_environment(context) -> None:
    context.plugin_router.discover_plugins()
    context.lifecycle = context.plugin_router.install_plugin(context.plugin_ref)
    plugin = context.native.installed[0]
    artifact = plugin.root / "traits" / "item"
    artifact.parent.mkdir()
    artifact.write_text("item", encoding="utf-8")
    (context.artifact_status_result,) = context.plugin_router.resolve_artifacts(
        "zpp.traits"
    )


@then("native adapter paths, ownership receipts, and artifact policies use only the isolated root")
def isolated_paths(context) -> None:
    assert context.lifecycle.after.runtime_root.is_relative_to(
        context.destination.resolve()
    ), (context.lifecycle.after.runtime_root, context.destination.resolve())
    assert context.artifact_status_result.paths[0].is_relative_to(
        context.destination.resolve()
    ), (context.artifact_status_result.paths, context.destination.resolve())
    assert all(
        request.environment[
            "CLAUDE_CONFIG_DIR"
        ] == str(context.destination.resolve())
        for request in context.native.calls
    ), [(request.argv, request.environment.get("CLAUDE_CONFIG_DIR")) for request in context.native.calls]
    assert all(
        request.cwd == context.destination.resolve()
        for request in context.native.calls
    )


@then("default agent and router state are neither read nor written")
def default_state_untouched(context) -> None:
    assert context.default_sentinel.read_text(encoding="utf-8") == "unchanged"
    assert not (context.home / ".agent-router").exists()


@then("the destination is not treated as an arbitrary plugin runtime directory")
def destination_is_environment(context) -> None:
    assert context.lifecycle.after.runtime_root != context.destination.resolve()
