from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import tomlkit
from tomlkit.container import Container
from tomlkit.items import AoT
from tomlkit.toml_document import TOMLDocument


JsonObject = dict[str, Any]
JsonHookFragment = dict[str, list[JsonObject]]
_PORTABLE_EVENTS = {
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "UserPromptSubmit",
    "Stop",
    "SubagentStart",
    "SubagentStop",
    "PreCompact",
    "SessionStart",
    "SessionEnd",
}


class HookDocumentError(ValueError):
    """A native hook document cannot be reconciled without loss."""


def parse_json_hook_source(source: bytes) -> JsonHookFragment:
    try:
        value = json.loads(source.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise HookDocumentError("hook source is not valid JSON") from error
    if not isinstance(value, dict) or set(value) != {"hooks"}:
        raise HookDocumentError("dedicated JSON hook source must contain only hooks")
    return _validated_json_hooks(value["hooks"])


def load_json_object(path: Path) -> JsonObject | None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise HookDocumentError(f"JSON destination is not a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise HookDocumentError(f"JSON destination is invalid: {path}") from error
    if not isinstance(value, dict):
        raise HookDocumentError("JSON destination must contain an object")
    if "hooks" in value:
        _validated_json_hooks(value["hooks"])
    return value


def reconcile_json_hooks(
    document: Mapping[str, Any] | None,
    fragment: Mapping[str, list[JsonObject]],
) -> JsonObject:
    validated = _validated_json_hooks(fragment)
    result = deepcopy(dict(document)) if document is not None else {}
    hooks = result.setdefault("hooks", {})
    current = _validated_json_hooks(hooks)
    for event, expected_groups in validated.items():
        groups = current.setdefault(event, [])
        for group in expected_groups:
            if group not in groups:
                groups.append(deepcopy(group))
    result["hooks"] = current
    return result


def remove_json_hooks(
    document: Mapping[str, Any],
    fragment: Mapping[str, list[JsonObject]],
) -> JsonObject:
    validated = _validated_json_hooks(fragment)
    result = deepcopy(dict(document))
    hooks = _validated_json_hooks(result.get("hooks", {}))
    for event, owned_groups in validated.items():
        groups = hooks.get(event)
        if groups is None or any(group not in groups for group in owned_groups):
            raise HookDocumentError("owned hook fragment is missing or modified")
        for group in owned_groups:
            groups.remove(group)
        if not groups:
            del hooks[event]
    if hooks:
        result["hooks"] = hooks
    else:
        result.pop("hooks", None)
    return result


def serialize_json(document: Mapping[str, Any]) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def parse_kimi_hook_source(source: bytes) -> list[JsonObject]:
    document = _parse_toml(source)
    if set(document) != {"hooks"}:
        raise HookDocumentError("dedicated Kimi hook source must contain only hooks")
    return _validated_kimi_hooks(document["hooks"])


def reconcile_kimi_hooks(
    source: bytes | TOMLDocument | None,
    fragment: list[JsonObject],
) -> TOMLDocument:
    expected = _validated_kimi_hooks(fragment)
    result = _toml_document(source)
    if "hooks" not in result:
        result.add("hooks", tomlkit.aot())
    hooks = result["hooks"]
    current = _validated_kimi_hooks(hooks)
    assert isinstance(hooks, AoT)
    for entry in expected:
        if entry not in current:
            table = tomlkit.table()
            for key, value in entry.items():
                table.add(key, value)
            hooks.append(table)
            current.append(entry)
    return result


def remove_kimi_hooks(
    source: bytes | TOMLDocument,
    fragment: list[JsonObject],
) -> TOMLDocument:
    expected = _validated_kimi_hooks(fragment)
    result = _toml_document(source)
    hooks = result.get("hooks")
    current = _validated_kimi_hooks(hooks)
    assert isinstance(hooks, AoT)
    for entry in expected:
        try:
            index = current.index(entry)
        except ValueError as error:
            raise HookDocumentError("owned hook fragment is missing or modified") from error
        del hooks[index]
        del current[index]
    if not hooks:
        del result["hooks"]
    return result


def serialize_toml(document: TOMLDocument) -> bytes:
    return tomlkit.dumps(document).encode("utf-8")


def convert_portable_command_hooks(
    document: Mapping[str, Any],
    target: str,
) -> JsonObject:
    if target not in {"claude", "codex"}:
        raise HookDocumentError("hook conversion supports only Claude Code and Codex")
    if set(document) != {"hooks"}:
        raise HookDocumentError("portable hook configuration must contain only hooks")
    hooks = _validated_json_hooks(document["hooks"])
    for event, groups in hooks.items():
        if event not in _PORTABLE_EVENTS:
            raise HookDocumentError(f"event is not portable: {event}")
        for group in groups:
            if not set(group).issubset({"matcher", "hooks"}):
                raise HookDocumentError("matcher group contains nonportable fields")
            if "matcher" in group and not isinstance(group["matcher"], str):
                raise HookDocumentError("portable matcher must be a string")
            for handler in group["hooks"]:
                if set(handler) not in (
                    {"type", "command"},
                    {"type", "command", "timeout"},
                ):
                    raise HookDocumentError("handler contains nonportable fields")
                if handler.get("type") != "command" or not isinstance(
                    handler.get("command"), str
                ):
                    raise HookDocumentError("portable hooks require command handlers")
                timeout = handler.get("timeout")
                if timeout is not None and (
                    not isinstance(timeout, int) or isinstance(timeout, bool)
                ):
                    raise HookDocumentError("portable timeout must be an integer")
    return {"hooks": hooks}


def _validated_json_hooks(value: object) -> JsonHookFragment:
    if not isinstance(value, Mapping):
        raise HookDocumentError("native hooks value must be an object")
    result: JsonHookFragment = {}
    for event, groups in value.items():
        if not isinstance(event, str) or not isinstance(groups, list):
            raise HookDocumentError("native hook event groups are malformed")
        validated_groups: list[JsonObject] = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise HookDocumentError("native hook matcher group is malformed")
            if not all(isinstance(handler, dict) for handler in group["hooks"]):
                raise HookDocumentError("native hook handler is malformed")
            validated_groups.append(deepcopy(group))
        result[event] = validated_groups
    return result


def _parse_toml(source: bytes) -> TOMLDocument:
    try:
        return tomlkit.parse(source.decode("utf-8"))
    except (UnicodeError, tomlkit.exceptions.ParseError) as error:
        raise HookDocumentError("hook source is not valid TOML") from error


def _toml_document(source: bytes | TOMLDocument | None) -> TOMLDocument:
    if source is None:
        return tomlkit.document()
    if isinstance(source, bytes):
        return _parse_toml(source)
    return tomlkit.parse(tomlkit.dumps(source))


def _validated_kimi_hooks(value: object) -> list[JsonObject]:
    if not isinstance(value, (list, AoT)):
        raise HookDocumentError("Kimi hooks must be an array of tables")
    allowed = {"event", "matcher", "command", "timeout"}
    result: list[JsonObject] = []
    for item in value:
        if not isinstance(item, (dict, Container)):
            raise HookDocumentError("Kimi hook entry must be a table")
        entry = {str(key): val.unwrap() if hasattr(val, "unwrap") else val for key, val in item.items()}
        if not set(entry).issubset(allowed):
            raise HookDocumentError("Kimi hook contains unsupported fields")
        if not isinstance(entry.get("event"), str) or not isinstance(entry.get("command"), str):
            raise HookDocumentError("Kimi hook requires event and command strings")
        if "matcher" in entry and not isinstance(entry["matcher"], str):
            raise HookDocumentError("Kimi hook matcher must be a string")
        if "timeout" in entry and (
            not isinstance(entry["timeout"], int) or isinstance(entry["timeout"], bool)
        ):
            raise HookDocumentError("Kimi hook timeout must be an integer")
        result.append(entry)
    return result
