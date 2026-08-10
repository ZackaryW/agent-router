from pathlib import Path

from agent_router import Agent, AssetKind, HookTransition, LifecycleResult, Scope


def test_hook_transition_serializes_without_changing_conversion_meaning() -> None:
    ordinary = LifecycleResult(
        "inspect",
        AssetKind.HOOK,
        "session",
        Agent.CLAUDE,
        Scope.USER,
        Path("/tmp/settings.json"),
        "current",
    )
    restored = LifecycleResult(
        "install",
        AssetKind.HOOK,
        "session",
        Agent.CLAUDE,
        Scope.USER,
        Path("/tmp/settings.json"),
        "updated",
        converted=False,
        hook_transition=HookTransition.OWNED_RESTORED,
    )

    assert ordinary.to_dict()["hook_transition"] is None
    assert restored.to_dict()["hook_transition"] == "owned-restored"
    assert restored.converted is False
    assert restored.changed is True
