from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent_router.utils.mutation import atomic_write

_AGENTS = {"codex", "claude", "kimi", "pi"}
_ARTIFACT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


class PluginStateError(ValueError):
    """Router-owned plugin state is malformed or unsupported."""


@dataclass(frozen=True, slots=True)
class PluginStateKey:
    agent: str
    scope: str
    native_ref: str


@dataclass(frozen=True, slots=True)
class PluginOwnershipReceipt:
    key: PluginStateKey
    source: str | None


@dataclass(frozen=True, slots=True)
class ArtifactPolicyOverride:
    key: PluginStateKey
    artifact_id: str
    policy: Literal["enabled", "disabled"]


@dataclass(frozen=True, slots=True)
class PluginState:
    receipts: tuple[PluginOwnershipReceipt, ...] = ()
    overrides: tuple[ArtifactPolicyOverride, ...] = ()
    schema_version: int = 1


def plugin_state_path(state_root: Path) -> Path:
    return state_root / ".agent-router" / "plugins.json"


def load_plugin_state(path: Path) -> PluginState:
    if not path.exists() and not path.is_symlink():
        return PluginState()
    if path.is_symlink() or not path.is_file():
        raise PluginStateError(f"plugin state is not a regular file: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        state = _decode_state(document)
        _validate_state(state)
        return state
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        if isinstance(error, PluginStateError):
            raise
        raise PluginStateError(f"plugin state is invalid: {path}") from error


def serialize_plugin_state(state: PluginState) -> bytes:
    _validate_state(state)
    document = {
        "schema_version": state.schema_version,
        "receipts": [
            {
                "agent": receipt.key.agent,
                "scope": receipt.key.scope,
                "native_ref": receipt.key.native_ref,
                "source": receipt.source,
            }
            for receipt in state.receipts
        ],
        "overrides": [
            {
                "agent": override.key.agent,
                "scope": override.key.scope,
                "native_ref": override.key.native_ref,
                "artifact_id": override.artifact_id,
                "policy": override.policy,
            }
            for override in state.overrides
        ],
    }
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def put_receipt(state: PluginState, receipt: PluginOwnershipReceipt) -> PluginState:
    _validate_receipt(receipt)
    receipts = tuple(item for item in state.receipts if item.key != receipt.key) + (receipt,)
    result = PluginState(receipts, state.overrides, state.schema_version)
    _validate_state(result)
    return result


def remove_receipt(state: PluginState, key: PluginStateKey) -> PluginState:
    _validate_key(key)
    return PluginState(
        tuple(item for item in state.receipts if item.key != key),
        state.overrides,
        state.schema_version,
    )


def set_artifact_policy(
    state: PluginState, override: ArtifactPolicyOverride
) -> PluginState:
    _validate_override(override)
    overrides = tuple(
        item
        for item in state.overrides
        if (item.key, item.artifact_id) != (override.key, override.artifact_id)
    ) + (override,)
    result = PluginState(state.receipts, overrides, state.schema_version)
    _validate_state(result)
    return result


def clear_artifact_policy(
    state: PluginState, key: PluginStateKey, artifact_id: str
) -> PluginState:
    _validate_key(key)
    _validate_artifact_id(artifact_id)
    return PluginState(
        state.receipts,
        tuple(
            item
            for item in state.overrides
            if (item.key, item.artifact_id) != (key, artifact_id)
        ),
        state.schema_version,
    )


def save_plugin_state(path: Path, state: PluginState) -> None:
    atomic_write(path, serialize_plugin_state(state))


def _decode_state(value: object) -> PluginState:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "receipts",
        "overrides",
    }:
        raise PluginStateError("plugin state document has unexpected fields")
    if value["schema_version"] != 1:
        raise PluginStateError("unsupported plugin state schema")
    receipts_value = value["receipts"]
    overrides_value = value["overrides"]
    if not isinstance(receipts_value, list) or not isinstance(overrides_value, list):
        raise PluginStateError("plugin state collections must be arrays")
    receipts = tuple(_decode_receipt(item) for item in receipts_value)
    overrides = tuple(_decode_override(item) for item in overrides_value)
    return PluginState(receipts, overrides)


def _decode_receipt(value: object) -> PluginOwnershipReceipt:
    if not isinstance(value, dict) or set(value) != {
        "agent",
        "scope",
        "native_ref",
        "source",
    }:
        raise PluginStateError("plugin receipt has unexpected fields")
    key = PluginStateKey(value["agent"], value["scope"], value["native_ref"])
    source = value["source"]
    if source is not None and (not isinstance(source, str) or not source):
        raise PluginStateError("plugin receipt source must be a non-empty string")
    return PluginOwnershipReceipt(key, source)


def _decode_override(value: object) -> ArtifactPolicyOverride:
    if not isinstance(value, dict) or set(value) != {
        "agent",
        "scope",
        "native_ref",
        "artifact_id",
        "policy",
    }:
        raise PluginStateError("artifact override has unexpected fields")
    key = PluginStateKey(value["agent"], value["scope"], value["native_ref"])
    return ArtifactPolicyOverride(key, value["artifact_id"], value["policy"])


def _validate_state(state: PluginState) -> None:
    if state.schema_version != 1:
        raise PluginStateError("unsupported plugin state schema")
    for receipt in state.receipts:
        _validate_receipt(receipt)
    for override in state.overrides:
        _validate_override(override)
    if len({receipt.key for receipt in state.receipts}) != len(state.receipts):
        raise PluginStateError("plugin state contains duplicate receipts")
    if len({(item.key, item.artifact_id) for item in state.overrides}) != len(
        state.overrides
    ):
        raise PluginStateError("plugin state contains duplicate artifact overrides")


def _validate_receipt(receipt: PluginOwnershipReceipt) -> None:
    _validate_key(receipt.key)
    if receipt.source is not None and (
        not isinstance(receipt.source, str) or not receipt.source
    ):
        raise PluginStateError("plugin receipt source must be a non-empty string")


def _validate_override(override: ArtifactPolicyOverride) -> None:
    _validate_key(override.key)
    _validate_artifact_id(override.artifact_id)
    if override.policy not in {"enabled", "disabled"}:
        raise PluginStateError("artifact override policy must be enabled or disabled")


def _validate_key(key: PluginStateKey) -> None:
    if key.agent not in _AGENTS:
        raise PluginStateError("plugin state agent is invalid")
    if not isinstance(key.scope, str) or not key.scope:
        raise PluginStateError("plugin state scope must be a non-empty string")
    if not isinstance(key.native_ref, str) or not key.native_ref:
        raise PluginStateError("plugin native reference must be a non-empty string")


def _validate_artifact_id(artifact_id: str) -> None:
    if not isinstance(artifact_id, str) or not _ARTIFACT_ID.fullmatch(artifact_id):
        raise PluginStateError("artifact identifier is invalid")
