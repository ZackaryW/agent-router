from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType


class NativePluginDecodeError(ValueError):
    """Authoritative native plugin evidence has an unsupported shape."""


@dataclass(frozen=True, slots=True)
class NativePluginEvidence:
    native_ref: str
    scope: str
    source: str | None
    name: str
    installed_version: str | None
    available_version: str | None
    installed: bool
    activation: str
    runtime_root: Path | None
    details: Mapping[str, object]


def decode_codex_plugins(payload: str) -> tuple[NativePluginEvidence, ...]:
    document = _json(payload, "Codex")
    if not isinstance(document, dict) or set(document) != {"installed", "available"}:
        raise NativePluginDecodeError("Codex plugin inventory must contain installed and available")
    installed = _list(document["installed"], "Codex installed plugins")
    available = _list(document["available"], "Codex available plugins")
    return tuple(_decode_codex_entry(value, True) for value in installed) + tuple(
        _decode_codex_entry(value, False) for value in available
    )


def decode_claude_plugins(payload: str) -> tuple[NativePluginEvidence, ...]:
    document = _json(payload, "Claude Code")
    if isinstance(document, list):
        installed = document
        available: list[object] = []
    elif isinstance(document, dict) and set(document) == {"installed", "available"}:
        installed = _list(document["installed"], "Claude Code installed plugins")
        available = _list(document["available"], "Claude Code available plugins")
    else:
        raise NativePluginDecodeError("Claude Code plugin inventory has an unsupported shape")
    return tuple(_decode_claude_installed(value) for value in installed) + tuple(
        _decode_claude_available(value) for value in available
    )


def decode_kimi_plugins(state_root: Path) -> tuple[NativePluginEvidence, ...]:
    path = state_root / "plugins" / "installed.json"
    if not path.exists():
        return ()
    if path.is_symlink() or not path.is_file():
        raise NativePluginDecodeError(f"Kimi installed state is not a regular file: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise NativePluginDecodeError(f"Kimi installed state is invalid: {path}") from error
    if (
        not isinstance(document, dict)
        or set(document) != {"version", "plugins"}
        or document["version"] != 1
    ):
        raise NativePluginDecodeError("Kimi installed state has an unsupported schema")
    return tuple(
        _decode_kimi_entry(value)
        for value in _list(document["plugins"], "Kimi installed plugins")
    )


def decode_pi_packages(payload: str) -> tuple[NativePluginEvidence, ...]:
    lines = payload.splitlines()
    records: list[NativePluginEvidence] = []
    scope: str | None = None
    index = 0
    while index < len(lines):
        line = lines[index]
        if line == "User packages:":
            scope = "user"
            index += 1
            continue
        if line == "Project packages:":
            scope = "project"
            index += 1
            continue
        if not line.strip():
            index += 1
            continue
        if scope is None or not line.startswith("  ") or line.startswith("    "):
            raise NativePluginDecodeError("Pi package inventory has an unsupported shape")
        native_ref = line.strip()
        if index + 1 >= len(lines) or not lines[index + 1].startswith("    "):
            raise NativePluginDecodeError("Pi package inventory is missing a runtime root")
        root_text = lines[index + 1].strip()
        if not native_ref or not root_text:
            raise NativePluginDecodeError("Pi package inventory contains an empty field")
        records.append(
            NativePluginEvidence(
                native_ref=native_ref,
                scope=scope,
                source=native_ref.split(":", 1)[0] if ":" in native_ref else None,
                name=native_ref.rsplit("/", 1)[-1],
                installed_version=None,
                available_version=None,
                installed=True,
                activation="partial",
                runtime_root=Path(root_text),
                details=MappingProxyType({}),
            )
        )
        index += 2
    if not any(line in {"User packages:", "Project packages:"} for line in lines):
        raise NativePluginDecodeError("Pi package inventory has no supported scope section")
    return tuple(records)


def _decode_codex_entry(value: object, installed: bool) -> NativePluginEvidence:
    entry = _object(value, "Codex plugin")
    native_ref = _string(entry, "pluginId")
    name = _string(entry, "name")
    marketplace = _string(entry, "marketplaceName")
    if _boolean(entry, "installed") is not installed:
        raise NativePluginDecodeError("Codex plugin installed flag conflicts with its inventory")
    enabled = _optional_boolean(entry, "enabled")
    version = _optional_string(entry, "version")
    root = None
    if installed:
        source = _object(entry.get("source"), "Codex plugin source")
        root_value = source.get("path")
        if root_value is not None and not isinstance(root_value, str):
            raise NativePluginDecodeError("Codex plugin source path must be a string")
        root = Path(root_value) if root_value else None
    return NativePluginEvidence(
        native_ref=native_ref,
        scope="user",
        source=marketplace,
        name=name,
        installed_version=version if installed else None,
        available_version=None if installed else version,
        installed=installed,
        activation=("enabled" if enabled else "disabled") if enabled is not None else "unknown",
        runtime_root=root,
        details=MappingProxyType(dict(entry)),
    )


def _decode_claude_installed(value: object) -> NativePluginEvidence:
    entry = _object(value, "Claude Code installed plugin")
    native_ref = _string(entry, "id")
    scope = _string(entry, "scope")
    if scope not in {"user", "project", "local", "managed"}:
        raise NativePluginDecodeError("Claude Code plugin scope is unsupported")
    root = Path(_string(entry, "installPath"))
    name, source = _split_ref(native_ref)
    enabled = _boolean(entry, "enabled")
    return NativePluginEvidence(
        native_ref=native_ref,
        scope=scope,
        source=source,
        name=name,
        installed_version=_optional_string(entry, "version"),
        available_version=_optional_string(entry, "availableVersion"),
        installed=True,
        activation="enabled" if enabled else "disabled",
        runtime_root=root,
        details=MappingProxyType(dict(entry)),
    )


def _decode_claude_available(value: object) -> NativePluginEvidence:
    entry = _object(value, "Claude Code available plugin")
    native_ref = _string(entry, "pluginId")
    name = _string(entry, "name")
    source = _string(entry, "marketplaceName")
    return NativePluginEvidence(
        native_ref=native_ref,
        scope="user",
        source=source,
        name=name,
        installed_version=None,
        available_version=_optional_string(entry, "version"),
        installed=False,
        activation="unknown",
        runtime_root=None,
        details=MappingProxyType(dict(entry)),
    )


def _decode_kimi_entry(value: object) -> NativePluginEvidence:
    entry = _object(value, "Kimi plugin")
    native_ref = _string(entry, "id")
    root = Path(_string(entry, "root"))
    enabled = _boolean(entry, "enabled")
    source = _optional_string(entry, "originalSource") or _string(entry, "source")
    return NativePluginEvidence(
        native_ref=native_ref,
        scope="user",
        source=source,
        name=native_ref,
        installed_version=None,
        available_version=None,
        installed=True,
        activation="enabled" if enabled else "disabled",
        runtime_root=root,
        details=MappingProxyType(dict(entry)),
    )


def _json(payload: str, agent: str) -> object:
    try:
        return json.loads(payload)
    except json.JSONDecodeError as error:
        raise NativePluginDecodeError(f"{agent} plugin inventory is not valid JSON") from error


def _list(value: object, description: str) -> list[object]:
    if not isinstance(value, list):
        raise NativePluginDecodeError(f"{description} must be an array")
    return value


def _object(value: object, description: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise NativePluginDecodeError(f"{description} must be an object")
    return value


def _string(entry: Mapping[str, object], key: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value:
        raise NativePluginDecodeError(f"native plugin field {key} must be a non-empty string")
    return value


def _optional_string(entry: Mapping[str, object], key: str) -> str | None:
    value = entry.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise NativePluginDecodeError(f"native plugin field {key} must be a non-empty string")
    return value


def _boolean(entry: Mapping[str, object], key: str) -> bool:
    value = entry.get(key)
    if not isinstance(value, bool):
        raise NativePluginDecodeError(f"native plugin field {key} must be a Boolean")
    return value


def _optional_boolean(entry: Mapping[str, object], key: str) -> bool | None:
    value = entry.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise NativePluginDecodeError(f"native plugin field {key} must be a Boolean")
    return value


def _split_ref(native_ref: str) -> tuple[str, str | None]:
    if "@" not in native_ref:
        return native_ref, None
    return tuple(native_ref.rsplit("@", 1))  # type: ignore[return-value]
