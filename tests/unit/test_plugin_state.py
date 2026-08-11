from __future__ import annotations

import json

import pytest

from agent_router.utils.plugin_state import (
    ArtifactPolicyOverride,
    PluginOwnershipReceipt,
    PluginState,
    PluginStateEvidence,
    PluginStateError,
    PluginStateKey,
    clear_artifact_policy,
    load_plugin_state,
    load_plugin_state_evidence,
    plugin_state_locations,
    plugin_state_path,
    put_receipt,
    remove_receipt,
    save_plugin_state,
    serialize_plugin_state,
    set_artifact_policy,
)


def test_plugin_state_round_trips_stable_keys_without_version_or_root(tmp_path) -> None:
    key = PluginStateKey("claude", "project", "review@team")
    state = PluginState(
        receipts=(PluginOwnershipReceipt(key, "team"),),
        overrides=(ArtifactPolicyOverride(key, "zpp.traits", "disabled"),),
    )
    path = plugin_state_path(tmp_path)

    save_plugin_state(path, state)

    assert path == tmp_path / ".agent-router" / "plugins.json"
    assert load_plugin_state(path) == state
    assert not tuple(path.parent.glob(f".{path.name}.*"))


def test_plugin_state_updates_are_immutable_and_replace_matching_keys() -> None:
    key = PluginStateKey("codex", "user", "docs@internal")
    original = PluginState()

    with_receipt = put_receipt(original, PluginOwnershipReceipt(key, "internal"))
    replaced = put_receipt(with_receipt, PluginOwnershipReceipt(key, "replacement"))
    with_policy = set_artifact_policy(
        replaced, ArtifactPolicyOverride(key, "zpp.traits", "enabled")
    )
    replaced_policy = set_artifact_policy(
        with_policy, ArtifactPolicyOverride(key, "zpp.traits", "disabled")
    )

    assert original.receipts == ()
    assert replaced.receipts == (PluginOwnershipReceipt(key, "replacement"),)
    assert replaced_policy.overrides == (
        ArtifactPolicyOverride(key, "zpp.traits", "disabled"),
    )
    assert clear_artifact_policy(replaced_policy, key, "zpp.traits").overrides == ()
    assert remove_receipt(replaced, key).receipts == ()


@pytest.mark.parametrize(
    "document",
    [
        {"schema_version": 2, "receipts": [], "overrides": []},
        {"schema_version": 1, "receipts": [], "overrides": [], "extra": True},
        {
            "schema_version": 1,
            "receipts": [
                {
                    "agent": "unknown",
                    "scope": "user",
                    "native_ref": "x",
                    "source": None,
                }
            ],
            "overrides": [],
        },
        {
            "schema_version": 1,
            "receipts": [],
            "overrides": [
                {
                    "agent": "codex",
                    "scope": "user",
                    "native_ref": "x",
                    "artifact_id": "zpp.traits",
                    "policy": "inherit",
                }
            ],
        },
    ],
)
def test_plugin_state_rejects_malformed_documents_without_rewriting(tmp_path, document) -> None:
    path = plugin_state_path(tmp_path)
    path.parent.mkdir(parents=True)
    original = json.dumps(document)
    path.write_text(original, encoding="utf-8")

    with pytest.raises(PluginStateError):
        load_plugin_state(path)

    assert path.read_text(encoding="utf-8") == original


def test_plugin_state_rejects_duplicate_stable_keys() -> None:
    key = PluginStateKey("pi", "project", "npm:tools")
    state = PluginState(
        receipts=(
            PluginOwnershipReceipt(key, None),
            PluginOwnershipReceipt(key, "npm"),
        )
    )

    with pytest.raises(PluginStateError, match="duplicate"):
        serialize_plugin_state(state)


def test_absent_plugin_state_is_empty(tmp_path) -> None:
    assert load_plugin_state(plugin_state_path(tmp_path)) == PluginState()


def test_resolves_and_loads_current_plugin_state_evidence(tmp_path) -> None:
    locations = plugin_state_locations(
        state_root=tmp_path / ".z-agent-router", legacy_root=tmp_path
    )
    state = PluginState(
        receipts=(
            PluginOwnershipReceipt(PluginStateKey("codex", "user", "example"), None),
        )
    )
    locations.current.parent.mkdir(parents=True)
    locations.current.write_bytes(serialize_plugin_state(state))

    assert locations.current == tmp_path / ".z-agent-router" / "plugins.json"
    assert locations.legacy == tmp_path / ".agent-router" / "plugins.json"
    assert load_plugin_state_evidence(locations) == PluginStateEvidence(
        state, locations, "current"
    )


@pytest.mark.parametrize(
    ("present", "source"),
    [((), "none"), (("legacy",), "legacy"), (("current", "legacy"), "duplicate")],
)
def test_distinguishes_compatible_plugin_state_evidence_locations(
    tmp_path, present, source
) -> None:
    locations = plugin_state_locations(
        state_root=tmp_path / ".z-agent-router", legacy_root=tmp_path
    )
    state = PluginState(
        receipts=(
            PluginOwnershipReceipt(PluginStateKey("codex", "user", "example"), None),
        )
    )
    for selected in present:
        path = getattr(locations, selected)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(serialize_plugin_state(state))

    evidence = load_plugin_state_evidence(locations)

    assert evidence.state == (state if present else PluginState())
    assert evidence.source == source


def test_rejects_divergent_current_and_legacy_plugin_state(tmp_path) -> None:
    locations = plugin_state_locations(
        state_root=tmp_path / ".z-agent-router", legacy_root=tmp_path
    )
    current = PluginState(
        receipts=(
            PluginOwnershipReceipt(PluginStateKey("codex", "user", "current"), None),
        )
    )
    legacy = PluginState(
        receipts=(
            PluginOwnershipReceipt(PluginStateKey("codex", "user", "legacy"), None),
        )
    )
    for path, state in ((locations.current, current), (locations.legacy, legacy)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(serialize_plugin_state(state))

    with pytest.raises(PluginStateError, match="diverge"):
        load_plugin_state_evidence(locations)
