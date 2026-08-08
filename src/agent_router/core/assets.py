from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Literal

from agent_router.core.models import Agent, InvalidAssetError
from agent_router.utils.assets import (
    AssetError,
    AssetFile,
    collect_asset_tree,
    fingerprint_asset,
    parse_skill_document,
)
from agent_router.utils.native_hooks import (
    HookDocumentError,
    parse_json_hook_source,
    parse_kimi_hook_source,
)


_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_CLAUDE_SKILL_FIELDS = {"hooks", "context", "agent"}
_CODEX_EVENTS = {
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "PreCompact",
    "PostCompact",
    "UserPromptSubmit",
    "SubagentStart",
    "SubagentStop",
    "Stop",
    "SessionStart",
    "SessionEnd",
}
_CLAUDE_EVENTS = _CODEX_EVENTS - {"PostCompact"} | {
    "PostToolUseFailure",
    "Notification",
    "TeammateIdle",
    "TaskCompleted",
    "ConfigChange",
    "WorktreeCreate",
    "WorktreeRemove",
}
_CLAUDE_HANDLER_TYPES = {"command", "http", "mcp_tool", "prompt", "agent"}


@dataclass(frozen=True, slots=True)
class Skill:
    path: Path
    name: str
    files: tuple[AssetFile, ...]
    fingerprint: str
    compatible_agents: frozenset[Agent]

    @classmethod
    def from_path(cls, path: str | Path) -> Skill:
        source = Path(path)
        try:
            files = collect_asset_tree(source)
            documents = [item for item in files if item.relative_path == "SKILL.md"]
            if len(documents) != 1:
                raise AssetError("skill requires one root SKILL.md")
            metadata = parse_skill_document(documents[0].content)
        except (AssetError, OSError) as error:
            raise InvalidAssetError(str(error)) from error
        compatibility = (
            frozenset({Agent.CLAUDE})
            if _CLAUDE_SKILL_FIELDS.intersection(metadata)
            else frozenset(Agent)
        )
        return cls(
            source.resolve(),
            str(metadata["name"]),
            files,
            fingerprint_asset(files),
            compatibility,
        )


@dataclass(frozen=True, slots=True)
class Hook:
    path: Path
    name: str
    format: Literal["json", "toml", "pi-file", "pi-directory"]
    fragment: object
    files: tuple[AssetFile, ...]
    fingerprint: str
    compatible_agents: frozenset[Agent]

    @classmethod
    def from_path(
        cls,
        path: str | Path,
        *,
        source_agent: Agent | None = None,
    ) -> Hook:
        source = Path(path)
        if source.is_symlink():
            raise InvalidAssetError(f"hook source is a symbolic link: {source}")
        name = source.stem if source.is_file() else source.name
        if not _NAME.fullmatch(name):
            raise InvalidAssetError(f"hook name is invalid: {name}")
        try:
            if source.is_dir():
                files = collect_asset_tree(source)
                if not files or not any(
                    item.relative_path.endswith((".ts", ".js")) for item in files
                ):
                    raise AssetError("Pi extension directory requires a TypeScript or JavaScript module")
                return cls(
                    source.resolve(),
                    name,
                    "pi-directory",
                    None,
                    files,
                    fingerprint_asset(files),
                    frozenset({Agent.PI}),
                )
            if not source.is_file():
                raise AssetError(f"hook source is not a regular file: {source}")
            data = source.read_bytes()
            suffix = source.suffix.lower()
            if suffix == ".json":
                fragment = parse_json_hook_source(data)
                compatible = _json_compatibility(fragment)
                if source_agent is not None:
                    if source_agent not in compatible:
                        raise AssetError(
                            f"hook source is not valid for {source_agent.value}"
                        )
                    compatible = frozenset({source_agent})
                return cls(
                    source.resolve(),
                    name,
                    "json",
                    fragment,
                    (),
                    _fragment_fingerprint(fragment),
                    compatible,
                )
            if suffix == ".toml":
                fragment = parse_kimi_hook_source(data)
                return cls(
                    source.resolve(),
                    name,
                    "toml",
                    fragment,
                    (),
                    _fragment_fingerprint(fragment),
                    frozenset({Agent.KIMI}),
                )
            if suffix in {".ts", ".js"}:
                data.decode("utf-8")
                files = (AssetFile(source.name, data),)
                return cls(
                    source.resolve(),
                    name,
                    "pi-file",
                    None,
                    files,
                    fingerprint_asset(files),
                    frozenset({Agent.PI}),
                )
            raise AssetError("hook source format is unsupported or ambiguous")
        except (AssetError, HookDocumentError, OSError, UnicodeError) as error:
            raise InvalidAssetError(str(error)) from error


def fragment_fingerprint(fragment: object) -> str:
    return _fragment_fingerprint(fragment)


def _fragment_fingerprint(fragment: object) -> str:
    encoded = json.dumps(fragment, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def _json_compatibility(fragment: dict[str, list[dict[str, object]]]) -> frozenset[Agent]:
    events = set(fragment)
    handler_types = {
        str(handler.get("type"))
        for groups in fragment.values()
        for group in groups
        for handler in group["hooks"]
    }
    compatible: set[Agent] = set()
    if events.issubset(_CODEX_EVENTS) and handler_types.issubset({"command"}):
        compatible.add(Agent.CODEX)
    if events.issubset(_CLAUDE_EVENTS) and handler_types.issubset(_CLAUDE_HANDLER_TYPES):
        compatible.add(Agent.CLAUDE)
    if not compatible:
        raise HookDocumentError("JSON hook has no supported native agent")
    return frozenset(compatible)
