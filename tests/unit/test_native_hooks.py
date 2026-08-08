from copy import deepcopy

import pytest

from agent_router.utils.native_hooks import (
    convert_portable_command_hooks,
    HookDocumentError,
    parse_kimi_hook_source,
    parse_json_hook_source,
    reconcile_json_hooks,
    reconcile_kimi_hooks,
    remove_json_hooks,
    remove_kimi_hooks,
    serialize_toml,
)


FRAGMENT = {
    "PreToolUse": [
        {
            "matcher": "Bash",
            "hooks": [{"type": "command", "command": "check", "timeout": 5}],
        }
    ]
}


def test_reconciles_json_hooks_without_changing_unrelated_content() -> None:
    document = {
        "permissions": {"allow": ["Read"]},
        "hooks": {
            "SessionStart": [
                {"matcher": "startup", "hooks": [{"type": "command", "command": "hello"}]}
            ]
        },
    }
    original = deepcopy(document)

    reconciled = reconcile_json_hooks(document, FRAGMENT)

    assert reconciled["permissions"] == document["permissions"]
    assert reconciled["hooks"]["SessionStart"] == document["hooks"]["SessionStart"]
    assert reconciled["hooks"]["PreToolUse"] == FRAGMENT["PreToolUse"]
    assert document == original


def test_repeating_json_reconciliation_is_a_no_op() -> None:
    once = reconcile_json_hooks({}, FRAGMENT)

    assert reconcile_json_hooks(once, FRAGMENT) == once


def test_removes_only_the_exact_owned_json_fragment() -> None:
    document = reconcile_json_hooks(
        {"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "other"}]}]}},
        FRAGMENT,
    )

    removed = remove_json_hooks(document, FRAGMENT)

    assert removed == {
        "hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "other"}]}]}
    }


def test_rejects_removing_a_modified_json_fragment() -> None:
    document = reconcile_json_hooks({}, FRAGMENT)
    document["hooks"]["PreToolUse"][-1]["matcher"] = "Write"

    with pytest.raises(HookDocumentError, match="owned hook fragment"):
        remove_json_hooks(document, FRAGMENT)


def test_parses_a_native_json_hook_source() -> None:
    source = b'{"hooks":{"PreToolUse":[{"hooks":[{"type":"command","command":"check"}]}]}}'

    assert parse_json_hook_source(source) == {
        "PreToolUse": [{"hooks": [{"type": "command", "command": "check"}]}]
    }


KIMI_FRAGMENT = [
    {"event": "PreToolUse", "matcher": "shell", "command": "check", "timeout": 5}
]


def test_reconciles_kimi_hooks_without_changing_unrelated_content() -> None:
    source = b'# keep this comment\nmodel = "kimi"\n\n[[hooks]]\nevent = "SessionStart"\ncommand = "hello"\n'

    reconciled = reconcile_kimi_hooks(source, KIMI_FRAGMENT)
    rendered = serialize_toml(reconciled).decode("utf-8")

    assert "# keep this comment" in rendered
    assert 'model = "kimi"' in rendered
    assert 'command = "hello"' in rendered
    assert 'command = "check"' in rendered


def test_repeating_kimi_reconciliation_is_a_no_op() -> None:
    once = serialize_toml(reconcile_kimi_hooks(None, KIMI_FRAGMENT))

    twice = serialize_toml(reconcile_kimi_hooks(once, KIMI_FRAGMENT))

    assert twice == once


def test_removes_only_the_exact_owned_kimi_fragment() -> None:
    source = b'[[hooks]]\nevent = "SessionStart"\ncommand = "hello"\n'
    installed = serialize_toml(reconcile_kimi_hooks(source, KIMI_FRAGMENT))

    removed = serialize_toml(remove_kimi_hooks(installed, KIMI_FRAGMENT)).decode("utf-8")

    assert 'command = "hello"' in removed
    assert 'command = "check"' not in removed


def test_rejects_extra_kimi_hook_fields() -> None:
    source = b'[[hooks]]\nevent = "PreToolUse"\ncommand = "check"\nunknown = true\n'

    with pytest.raises(HookDocumentError, match="unsupported"):
        parse_kimi_hook_source(source)


def test_converts_the_portable_command_hook_subset() -> None:
    source = {"hooks": FRAGMENT}

    assert convert_portable_command_hooks(source, "codex") == source
    assert convert_portable_command_hooks(source, "claude") == source


@pytest.mark.parametrize(
    "source",
    [
        {"hooks": {"Notification": FRAGMENT["PreToolUse"]}},
        {"hooks": {"PreToolUse": [{"hooks": [{"type": "prompt", "prompt": "check"}]}]}},
        {
            "hooks": {
                "PreToolUse": [
                    {"hooks": [{"type": "command", "command": "check", "async": True}]}
                ]
            }
        },
    ],
)
def test_rejects_nonportable_conversion_content(source: dict[str, object]) -> None:
    with pytest.raises(HookDocumentError, match="portable"):
        convert_portable_command_hooks(source, "codex")


def test_rejects_conversion_to_a_non_json_agent() -> None:
    with pytest.raises(HookDocumentError, match="Claude Code and Codex"):
        convert_portable_command_hooks({"hooks": FRAGMENT}, "kimi")
