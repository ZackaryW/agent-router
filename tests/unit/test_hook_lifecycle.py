from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_router import (
    Agent,
    AgentRouter,
    ConflictError,
    Hook,
    HookTransition,
    UnsupportedAssetError,
)
from agent_router.utils.native_hooks import reconcile_json_hooks, serialize_json
from agent_router.utils import mutation


def _json_hook(root: Path, folder: str, command: str, matcher: str = "Bash") -> Hook:
    path = root / folder / "zpp-session.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": matcher,
                            "hooks": [{"type": "command", "command": command}],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    return Hook.from_path(path, source_agent=Agent.CLAUDE)


def _write_fragment(destination: Path, hook: Hook) -> None:
    destination.write_bytes(serialize_json(reconcile_json_hooks(None, hook.fragment)))


def test_shared_hook_analysis_covers_owned_and_predecessor_states(
    tmp_path: Path,
) -> None:
    current = _json_hook(tmp_path, "current", "zpp guard")
    older_owned = _json_hook(tmp_path, "owned", "zpp prior guard")
    predecessor = _json_hook(tmp_path, "legacy", "zpp codespace guard")
    destination = tmp_path / "settings.json"
    router = AgentRouter(Agent.CLAUDE, home=tmp_path)

    assert router.inspect_hook(current, destination=destination).status == "absent"

    _write_fragment(destination, predecessor)
    legacy = router.inspect_hook(
        current, predecessors=(predecessor,), destination=destination
    )
    assert (legacy.status, legacy.hook_transition) == (
        "outdated",
        HookTransition.LEGACY_REPLACED,
    )
    replaced = router.install_hook(
        current, predecessors=(predecessor,), destination=destination
    )
    assert (replaced.status, replaced.hook_transition) == (
        "updated",
        HookTransition.LEGACY_REPLACED,
    )

    document = json.loads(destination.read_text(encoding="utf-8"))
    destination.write_bytes(
        serialize_json(reconcile_json_hooks(document, predecessor.fragment))
    )
    pruning = router.inspect_hook(
        current, predecessors=(predecessor,), destination=destination
    )
    assert (pruning.status, pruning.hook_transition) == (
        "outdated",
        HookTransition.LEGACY_PRUNED,
    )

    router.install_hook(
        current, predecessors=(predecessor,), destination=destination
    )
    assert router.inspect_hook(current, destination=destination).status == "current"

    destination.write_text('{"theme":"dark","hooks":{}}\n', encoding="utf-8")
    missing = router.inspect_hook(current, destination=destination)
    assert (missing.status, missing.hook_transition) == (
        "outdated",
        HookTransition.OWNED_RESTORED,
    )

    restored = router.install_hook(current, destination=destination)
    assert restored.hook_transition is HookTransition.OWNED_RESTORED
    assert json.loads(destination.read_text(encoding="utf-8"))["theme"] == "dark"

    destination.unlink()
    router.install_hook(older_owned, destination=destination)
    outdated = router.inspect_hook(current, destination=destination)
    assert (outdated.status, outdated.hook_transition) == ("outdated", None)


def test_shared_hook_analysis_rejects_ambiguous_predecessors(tmp_path: Path) -> None:
    current = _json_hook(tmp_path, "current", "zpp guard")
    predecessor = _json_hook(tmp_path, "legacy", "zpp codespace guard")
    other = _json_hook(tmp_path, "older", "zpp older guard", matcher="Write")
    destination = tmp_path / "settings.json"
    document = reconcile_json_hooks(None, predecessor.fragment)
    document = reconcile_json_hooks(document, other.fragment)
    destination.write_bytes(serialize_json(document))
    router = AgentRouter(Agent.CLAUDE, home=tmp_path)

    assert (
        router.inspect_hook(
            current,
            predecessors=(predecessor, other),
            destination=destination,
        ).status
        == "conflict"
    )
    with pytest.raises(ConflictError):
        router.install_hook(
            current,
            predecessors=(predecessor, other),
            destination=destination,
        )

    partial = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": "modified"}],
                }
            ]
        }
    }
    destination.write_text(json.dumps(partial), encoding="utf-8")
    assert (
        router.inspect_hook(
            current, predecessors=(predecessor,), destination=destination
        ).status
        == "conflict"
    )


def test_shared_hook_analysis_rejects_incompatible_predecessor(
    tmp_path: Path,
) -> None:
    current = _json_hook(tmp_path, "current", "zpp guard")
    kimi_path = tmp_path / "legacy" / "zpp-session.toml"
    kimi_path.parent.mkdir(parents=True)
    kimi_path.write_text(
        '[[hooks]]\nevent = "PreToolUse"\ncommand = "legacy"\n',
        encoding="utf-8",
    )
    incompatible = Hook.from_path(kimi_path)
    router = AgentRouter(Agent.CLAUDE, home=tmp_path)

    with pytest.raises(UnsupportedAssetError):
        router.install_hook(current, predecessors=(incompatible,))


def test_current_shared_hook_does_not_count_its_subset_predecessor(
    tmp_path: Path,
) -> None:
    current_path = tmp_path / "current" / "zpp-session.json"
    current_path.parent.mkdir(parents=True)
    current_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [{"type": "command", "command": "guard"}],
                        }
                    ],
                    "SessionStart": [
                        {"hooks": [{"type": "command", "command": "resolve"}]}
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    predecessor_path = tmp_path / "legacy" / "resolution.json"
    predecessor_path.parent.mkdir(parents=True)
    predecessor_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [
                        {"hooks": [{"type": "command", "command": "resolve"}]}
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    current = Hook.from_path(current_path, source_agent=Agent.CLAUDE)
    predecessor = Hook.from_path(predecessor_path, source_agent=Agent.CLAUDE)
    destination = tmp_path / "settings.json"
    router = AgentRouter(Agent.CLAUDE, home=tmp_path)
    router.install_hook(current, destination=destination)

    inspection = router.inspect_hook(
        current, predecessors=(predecessor,), destination=destination
    )

    assert (inspection.status, inspection.hook_transition) == ("current", None)


def test_kimi_shared_hook_replaces_one_exact_predecessor(tmp_path: Path) -> None:
    current_path = tmp_path / "current" / "zpp-session.toml"
    current_path.parent.mkdir(parents=True)
    current_path.write_text(
        '[[hooks]]\nevent = "SessionStart"\ncommand = "current"\n',
        encoding="utf-8",
    )
    predecessor_path = tmp_path / "legacy" / "session.toml"
    predecessor_path.parent.mkdir(parents=True)
    predecessor_path.write_text(
        '[[hooks]]\nevent = "SessionStart"\ncommand = "legacy"\n',
        encoding="utf-8",
    )
    current = Hook.from_path(current_path)
    predecessor = Hook.from_path(predecessor_path)
    destination = tmp_path / "kimi.jsonl"
    destination.write_bytes(predecessor_path.read_bytes())
    router = AgentRouter(Agent.KIMI, home=tmp_path)

    inspection = router.inspect_hook(
        current, predecessors=(predecessor,), destination=destination
    )
    result = router.install_hook(
        current, predecessors=(predecessor,), destination=destination
    )

    assert inspection.hook_transition is HookTransition.LEGACY_REPLACED
    assert result.hook_transition is HookTransition.LEGACY_REPLACED
    assert 'command = "current"' in destination.read_text(encoding="utf-8")
    assert 'command = "legacy"' not in destination.read_text(encoding="utf-8")


def _pi_file(root: Path, folder: str, name: str, content: str) -> Hook:
    path = root / folder / name
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    return Hook.from_path(path)


def _pi_directory(root: Path, folder: str, name: str, content: str) -> Hook:
    path = root / folder / name
    path.mkdir(parents=True)
    (path / "index.ts").write_text(content, encoding="utf-8")
    return Hook.from_path(path)


def test_dedicated_hook_analysis_replaces_historical_targets_and_restores_owned(
    tmp_path: Path,
) -> None:
    current = _pi_file(
        tmp_path, "current", "zpp-session.ts", "export default 'current'"
    )
    predecessor = _pi_file(
        tmp_path, "legacy", "zpp.ts", "export default 'legacy'"
    )
    destination = tmp_path / "extensions"
    destination.mkdir()
    (destination / "zpp.ts").write_text("export default 'legacy'", encoding="utf-8")
    router = AgentRouter(Agent.PI, home=tmp_path)

    inspected = router.inspect_hook(
        current, predecessors=(predecessor,), destination=destination
    )
    assert (inspected.status, inspected.hook_transition) == (
        "outdated",
        HookTransition.LEGACY_REPLACED,
    )
    installed = router.install_hook(
        current, predecessors=(predecessor,), destination=destination
    )
    assert installed.hook_transition is HookTransition.LEGACY_REPLACED
    assert (destination / "zpp-session.ts").read_text() == "export default 'current'"
    assert not (destination / "zpp.ts").exists()

    (destination / "zpp-session.ts").unlink()
    missing = router.inspect_hook(current, destination=destination)
    assert (missing.status, missing.hook_transition) == (
        "outdated",
        HookTransition.OWNED_RESTORED,
    )
    restored = router.install_hook(current, destination=destination)
    assert restored.hook_transition is HookTransition.OWNED_RESTORED


def test_dedicated_hook_analysis_handles_directory_predecessor(tmp_path: Path) -> None:
    current = _pi_directory(
        tmp_path, "current", "zpp-session", "export default 'current'"
    )
    predecessor = _pi_directory(
        tmp_path, "legacy", "zpp", "export default 'legacy'"
    )
    destination = tmp_path / "extensions"
    (destination / "zpp").mkdir(parents=True)
    (destination / "zpp/index.ts").write_text(
        "export default 'legacy'", encoding="utf-8"
    )
    router = AgentRouter(Agent.PI, home=tmp_path)

    result = router.install_hook(
        current, predecessors=(predecessor,), destination=destination
    )

    assert result.hook_transition is HookTransition.LEGACY_REPLACED
    assert (destination / "zpp-session/index.ts").is_file()
    assert not (destination / "zpp").exists()


def test_dedicated_hook_analysis_rejects_modified_predecessor_target(
    tmp_path: Path,
) -> None:
    current = _pi_file(
        tmp_path, "current", "zpp-session.ts", "export default 'current'"
    )
    predecessor = _pi_file(
        tmp_path, "legacy", "zpp.ts", "export default 'legacy'"
    )
    destination = tmp_path / "extensions"
    destination.mkdir()
    (destination / "zpp.ts").write_text("export default 'modified'", encoding="utf-8")
    router = AgentRouter(Agent.PI, home=tmp_path)

    assert (
        router.inspect_hook(
            current, predecessors=(predecessor,), destination=destination
        ).status
        == "conflict"
    )
    with pytest.raises(ConflictError):
        router.install_hook(
            current, predecessors=(predecessor,), destination=destination
        )


def test_uninstall_removes_only_stale_shared_ownership(tmp_path: Path) -> None:
    current = _json_hook(tmp_path, "current", "zpp guard")
    destination = tmp_path / "settings.json"
    router = AgentRouter(Agent.CLAUDE, home=tmp_path)
    router.install_hook(current, destination=destination)
    destination.write_text('{"hooks":{},"theme":"dark"}\n', encoding="utf-8")
    before = destination.read_bytes()

    result = router.uninstall_hook(current.name, destination=destination)

    assert result.hook_transition is HookTransition.OWNED_REMOVED
    assert destination.read_bytes() == before


def test_uninstall_rejects_partially_modified_shared_hook(tmp_path: Path) -> None:
    current = _json_hook(tmp_path, "current", "zpp guard")
    destination = tmp_path / "settings.json"
    router = AgentRouter(Agent.CLAUDE, home=tmp_path)
    router.install_hook(current, destination=destination)
    destination.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [{"type": "command", "command": "modified"}],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    before = destination.read_bytes()

    with pytest.raises(ConflictError):
        router.uninstall_hook(current.name, destination=destination)

    assert destination.read_bytes() == before


def test_uninstall_removes_only_stale_dedicated_ownership(tmp_path: Path) -> None:
    current = _pi_file(
        tmp_path, "current", "zpp-session.ts", "export default 'current'"
    )
    destination = tmp_path / "extensions"
    router = AgentRouter(Agent.PI, home=tmp_path)
    router.install_hook(current, destination=destination)
    (destination / "zpp-session.ts").unlink()

    result = router.uninstall_hook(current.name, destination=destination)

    assert result.hook_transition is HookTransition.OWNED_REMOVED


def test_uninstall_rejects_modified_dedicated_hook(tmp_path: Path) -> None:
    current = _pi_file(
        tmp_path, "current", "zpp-session.ts", "export default 'current'"
    )
    destination = tmp_path / "extensions"
    router = AgentRouter(Agent.PI, home=tmp_path)
    router.install_hook(current, destination=destination)
    target = destination / "zpp-session.ts"
    target.write_text("export default 'modified'", encoding="utf-8")

    with pytest.raises(ConflictError):
        router.uninstall_hook(current.name, destination=destination)

    assert target.read_text(encoding="utf-8") == "export default 'modified'"


def _fail_ownership_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_atomic_write = mutation.atomic_write

    def injected(path: Path, content: bytes) -> None:
        if ".z-agent-router" in path.parts:
            raise OSError("injected ownership failure")
        real_atomic_write(path, content)

    monkeypatch.setattr(mutation, "atomic_write", injected)


def test_shared_predecessor_transition_is_atomic_on_ownership_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = _json_hook(tmp_path, "current", "zpp guard")
    predecessor = _json_hook(tmp_path, "legacy", "zpp codespace guard")
    destination = tmp_path / "settings.json"
    _write_fragment(destination, predecessor)
    before = destination.read_bytes()
    _fail_ownership_write(monkeypatch)

    with pytest.raises(OSError, match="injected ownership failure"):
        AgentRouter(Agent.CLAUDE, home=tmp_path).install_hook(
            current, predecessors=(predecessor,), destination=destination
        )

    assert destination.read_bytes() == before
    assert not (tmp_path / ".z-agent-router").exists()


def test_dedicated_predecessor_transition_is_atomic_on_ownership_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = _pi_file(
        tmp_path, "current", "zpp-session.ts", "export default 'current'"
    )
    predecessor = _pi_file(
        tmp_path, "legacy", "zpp.ts", "export default 'legacy'"
    )
    destination = tmp_path / "extensions"
    destination.mkdir()
    legacy_target = destination / "zpp.ts"
    legacy_target.write_text("export default 'legacy'", encoding="utf-8")
    _fail_ownership_write(monkeypatch)

    with pytest.raises(OSError, match="injected ownership failure"):
        AgentRouter(Agent.PI, home=tmp_path).install_hook(
            current, predecessors=(predecessor,), destination=destination
        )

    assert legacy_target.read_text(encoding="utf-8") == "export default 'legacy'"
    assert not (destination / "zpp-session.ts").exists()
    assert not (tmp_path / ".z-agent-router").exists()
