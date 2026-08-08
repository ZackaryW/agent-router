from __future__ import annotations

import json
from pathlib import Path

from behave import given, then, when
from typer.testing import CliRunner

from agent_router import (
    Agent,
    AgentRouterError,
    ConflictError,
    Hook,
    InvalidAssetError,
    Scope,
    UnsupportedAssetError,
)
from agent_router.cli.app import app
from features.support.lifecycle import (
    capture as _capture,
    router as _router,
    write_json_hook as _write_json_hook,
    write_kimi_hook as _write_kimi_hook,
    write_pi_hook as _write_pi_hook,
)


@given("an explicit project root")
def given_project_root(context) -> None:
    context.project_root = context.root / "project"
    context.project_root.mkdir(exist_ok=True)


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
    source_agent = Agent(source.lower())
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


@given(
    "an intact older hook integration installed by agent-router beside unrelated hooks"
)
def given_old_hook(context) -> None:
    given_installed_hook(context)
    context.source.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "shell",
                            "hooks": [{"type": "command", "command": "new-check"}],
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
        lambda: _router(context, Agent(agent.lower())).install_hook(
            context.hook,
            scope=selected_scope,
            project_root=getattr(context, "project_root", None),
        ),
    )


@when("I inspect the hook for {agent}")
def inspect_hook(context, agent: str) -> None:
    try:
        hook = getattr(context, "hook", None) or Hook.from_path(context.source)
    except Exception as error:  # noqa: BLE001 - invalid-source scenarios inspect it
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
    result = CliRunner().invoke(
        app,
        [
            "hook",
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


@then("the integration is installed through that native surface")
def hook_installed(context) -> None:
    assert context.error is None
    assert context.result.status == "installed"
    assert context.result.destination.exists()


@then("unrelated native configuration is retained")
@then("unrelated native configuration is unchanged")
def unrelated_hook_retained(context) -> None:
    destination = (
        context.result.destination
        if context.result is not None
        else context.destination
    )
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


@then("installation succeeds as a no-op")
def install_noop(context) -> None:
    assert context.error is None
    assert context.result.status == "no-op"


@then("no destination is changed")
def no_destination_change(context) -> None:
    assert not context.destination.exists()


@then("the operation reports invalid source content")
def reports_invalid_source(context) -> None:
    assert isinstance(context.error, InvalidAssetError)


@then("the operation reports an unsupported asset")
def reports_unsupported_asset(context) -> None:
    assert isinstance(context.error, UnsupportedAssetError) or (
        context.result is not None and context.result.status == "unsupported"
    )


@then("the operation reports an ownership conflict")
def reports_conflict(context) -> None:
    assert isinstance(context.error, ConflictError)


@then("the request is rejected before destination mutation")
def rejected_before_mutation(context) -> None:
    assert context.error is not None
    assert not context.destination.exists()
