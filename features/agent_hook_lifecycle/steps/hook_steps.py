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
    HookTransition,
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


def _predecessor_fixture(context, agent: Agent = Agent.CLAUDE) -> None:
    context.agent = agent
    current_root = context.root / "current"
    legacy_root = context.root / "legacy"
    current_root.mkdir(exist_ok=True)
    legacy_root.mkdir(exist_ok=True)
    if agent in {Agent.CLAUDE, Agent.CODEX}:
        current_path = _write_json_hook(current_root)
        predecessor_path = _write_json_hook(legacy_root)
        current_path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "shell",
                                "hooks": [
                                    {"type": "command", "command": "current-check"}
                                ],
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        predecessor_path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "shell",
                                "hooks": [
                                    {"type": "command", "command": "legacy-check"}
                                ],
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        context.destination = context.root / f"{agent.value}-settings.json"
        context.destination.write_text(
            json.dumps(
                {
                    "permissions": {"allow": ["Read"]},
                    "hooks": json.loads(
                        predecessor_path.read_text(encoding="utf-8")
                    )["hooks"],
                }
            ),
            encoding="utf-8",
        )
        context.current_target = context.destination
        context.predecessor_target = context.destination
        context.current = Hook.from_path(current_path, source_agent=agent)
        context.predecessor = Hook.from_path(predecessor_path, source_agent=agent)
    elif agent is Agent.KIMI:
        current_path = _write_kimi_hook(current_root)
        predecessor_path = _write_kimi_hook(legacy_root)
        current_path.write_text(
            '[[hooks]]\nevent = "PreToolUse"\nmatcher = "shell"\ncommand = "current-check"\n',
            encoding="utf-8",
        )
        predecessor_path.write_text(
            '[[hooks]]\nevent = "PreToolUse"\nmatcher = "shell"\ncommand = "legacy-check"\n',
            encoding="utf-8",
        )
        context.destination = context.root / "kimi-hooks.toml"
        context.destination.write_text(
            'theme = "dark"\n\n' + predecessor_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        context.current_target = context.destination
        context.predecessor_target = context.destination
        context.current = Hook.from_path(current_path)
        context.predecessor = Hook.from_path(predecessor_path)
    else:
        current_path = _write_pi_hook(current_root)
        predecessor_path = _write_pi_hook(legacy_root, "legacy-reviewer")
        current_path.write_text("export default 'current-check'\n", encoding="utf-8")
        predecessor_path.write_text("export default 'legacy-check'\n", encoding="utf-8")
        context.destination = context.root / "extensions"
        context.destination.mkdir()
        context.predecessor_target = context.destination / predecessor_path.name
        context.predecessor_target.write_bytes(predecessor_path.read_bytes())
        (context.destination / "unrelated.ts").write_text(
            "export default 'unrelated'\n", encoding="utf-8"
        )
        context.current_target = context.destination / current_path.name
        context.current = Hook.from_path(current_path)
        context.predecessor = Hook.from_path(predecessor_path)
    context.hook = context.current
    context.predecessors = (context.predecessor,)
    context.before_native = context.destination.read_bytes() if context.destination.is_file() else None


@given("an exact native {agent} predecessor is present for a current hook")
def given_exact_predecessor(context, agent: str) -> None:
    _predecessor_fixture(context, Agent(agent.lower()))


@given("unrelated native configuration exists beside it")
def given_unrelated_predecessor_configuration(context) -> None:
    if context.agent in {Agent.CLAUDE, Agent.CODEX}:
        document = json.loads(context.destination.read_text(encoding="utf-8"))
        assert document["permissions"] == {"allow": ["Read"]}
    elif context.agent is Agent.KIMI:
        assert 'theme = "dark"' in context.destination.read_text(encoding="utf-8")
    else:
        assert (context.destination / "unrelated.ts").is_file()


@given("a current owned hook and one exact declared predecessor coexist")
def given_current_and_predecessor(context) -> None:
    _predecessor_fixture(context)
    context.destination.unlink()
    router = _router(context, context.agent)
    router.install_hook(context.current, destination=context.destination)
    document = json.loads(context.destination.read_text(encoding="utf-8"))
    legacy_group = json.loads(
        context.predecessor.path.read_text(encoding="utf-8")
    )["hooks"]["PreToolUse"][0]
    document["hooks"]["PreToolUse"].append(legacy_group)
    context.destination.write_text(json.dumps(document), encoding="utf-8")


@given("valid ownership identifies a hook whose complete native projection is absent")
def given_owned_missing_hook(context) -> None:
    _predecessor_fixture(context)
    context.destination.unlink()
    router = _router(context, context.agent)
    router.install_hook(context.current, destination=context.destination)
    document = json.loads(context.destination.read_text(encoding="utf-8"))
    document["hooks"] = {}
    document["theme"] = "dark"
    context.destination.write_text(json.dumps(document), encoding="utf-8")
    context.predecessors = ()


@given("no recognized hook structure overlaps ambiguously")
def given_no_ambiguous_overlap(context) -> None:
    assert _router(context, context.agent).inspect_hook(
        context.current, destination=context.destination
    ).hook_transition is HookTransition.OWNED_RESTORED


@given("declared predecessor evidence is {state}")
def given_ambiguous_predecessor(context, state: str) -> None:
    _predecessor_fixture(context)
    base = {
        "matcher": "shell",
        "hooks": [{"type": "command", "command": "legacy-check"}],
    }
    if state == "partially present":
        document = {"hooks": {"PreToolUse": [{"matcher": "shell", "hooks": []}]}}
    elif state == "duplicated":
        document = {"hooks": {"PreToolUse": [base, base]}}
    elif state == "placed under the wrong native group":
        document = {"hooks": {"SessionStart": [base]}}
    elif state == "present for more than one predecessor":
        second_path = context.root / "older" / "reviewer.json"
        second_path.parent.mkdir()
        second_group = {
            "matcher": "write",
            "hooks": [{"type": "command", "command": "older-check"}],
        }
        second_path.write_text(
            json.dumps({"hooks": {"PreToolUse": [second_group]}}),
            encoding="utf-8",
        )
        context.predecessors = context.predecessors + (
            Hook.from_path(second_path, source_agent=Agent.CLAUDE),
        )
        document = {"hooks": {"PreToolUse": [base, second_group]}}
    else:
        document = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "shell",
                        "hooks": [{"type": "command", "command": "changed"}],
                    }
                ]
            }
        }
    context.destination.write_text(json.dumps(document), encoding="utf-8")
    context.before_native = context.destination.read_bytes()


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
        lambda: _router(context, getattr(context, "agent", Agent.CODEX)).uninstall_hook(
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


@when("I install the current hook with that predecessor declared")
def install_with_predecessor(context) -> None:
    _capture(
        context,
        lambda: _router(context, context.agent).install_hook(
            context.current,
            predecessors=context.predecessors,
            destination=context.destination,
        ),
    )


@when("I explicitly install the current hook")
def install_owned_missing_hook(context) -> None:
    _capture(
        context,
        lambda: _router(context, context.agent).install_hook(
            context.current, destination=context.destination
        ),
    )


@when("I inspect or install the current hook")
def inspect_ambiguous_predecessor(context) -> None:
    _capture(
        context,
        lambda: _router(context, context.agent).inspect_hook(
            context.current,
            predecessors=context.predecessors,
            destination=context.destination,
        ),
    )


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


@then("only the exact predecessor is removed")
def exact_predecessor_removed(context) -> None:
    if context.agent is Agent.PI:
        assert not context.predecessor_target.exists()
    else:
        assert "legacy-check" not in context.destination.read_text(encoding="utf-8")


@then("the current hook and its ownership evidence are installed atomically")
@then("the current hook and its ownership evidence are retained")
def current_hook_is_owned(context) -> None:
    inspection = _router(context, context.agent).inspect_hook(
        context.current, destination=context.destination
    )
    assert inspection.status == "current"
    if context.agent is Agent.PI:
        assert context.current_target.is_file()
    else:
        assert "current-check" in context.destination.read_text(encoding="utf-8")


@then("the result reports a legacy-replaced transition without source conversion")
def reports_legacy_replaced(context) -> None:
    assert context.error is None
    assert context.result.hook_transition is HookTransition.LEGACY_REPLACED
    assert context.result.converted is False


@then("the result reports a legacy-pruned transition")
def reports_legacy_pruned(context) -> None:
    assert context.error is None
    assert context.result.hook_transition is HookTransition.LEGACY_PRUNED


@then("the current hook is restored without changing unrelated configuration")
def restored_hook_preserves_unrelated(context) -> None:
    assert context.error is None
    document = json.loads(context.destination.read_text(encoding="utf-8"))
    assert document["theme"] == "dark"
    assert "current-check" in context.destination.read_text(encoding="utf-8")


@then("the result reports an owned-restored transition")
def reports_owned_restored(context) -> None:
    assert context.result.hook_transition is HookTransition.OWNED_RESTORED


@then("only the stale ownership evidence is removed")
def stale_ownership_removed(context) -> None:
    assert context.error is None
    assert _router(context, context.agent).inspect_hook(
        context.current, destination=context.destination
    ).status == "absent"


@then("the absent hook is not recreated")
def absent_hook_not_recreated(context) -> None:
    document = json.loads(context.destination.read_text(encoding="utf-8"))
    assert document["hooks"] == {}
    assert document["theme"] == "dark"


@then("the result reports an owned-removed transition")
def reports_owned_removed(context) -> None:
    assert context.result.hook_transition is HookTransition.OWNED_REMOVED


@then("the operation reports a conflict before mutation")
def predecessor_conflict(context) -> None:
    assert context.error is None
    assert context.result.status == "conflict"
    assert context.destination.read_bytes() == context.before_native


@then(
    "no native content is claimed from a command prefix, filename, event alone, or destination"
)
def ambiguous_native_content_unclaimed(context) -> None:
    assert context.destination.read_bytes() == context.before_native
    assert context.result.status == "conflict"
