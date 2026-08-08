from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import yaml

_SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class AssetError(ValueError):
    """The supplied source is not a safe supported asset."""


@dataclass(frozen=True, slots=True)
class AssetFile:
    relative_path: str
    content: bytes


def collect_asset_tree(root: Path) -> tuple[AssetFile, ...]:
    if root.is_symlink():
        raise AssetError(f"asset root is a symbolic link: {root}")
    if not root.is_dir():
        raise AssetError(f"asset root is not a directory: {root}")

    files: list[AssetFile] = []
    for path in sorted(
        root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()
    ):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise AssetError(f"asset contains a symbolic link: {relative}")
        if path.is_file():
            files.append(AssetFile(relative, path.read_bytes()))
        elif not path.is_dir():
            raise AssetError(f"asset contains an unsupported entry: {relative}")
    return tuple(files)


def fingerprint_asset(files: Iterable[AssetFile]) -> str:
    digest = sha256()
    for item in sorted(files, key=lambda file: file.relative_path):
        path = item.relative_path.encode("utf-8")
        digest.update(len(path).to_bytes(8, "big"))
        digest.update(path)
        digest.update(len(item.content).to_bytes(8, "big"))
        digest.update(item.content)
    return digest.hexdigest()


def parse_skill_document(source: bytes) -> Mapping[str, object]:
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as error:
        raise AssetError("SKILL.md is not valid UTF-8") from error
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.startswith("---\n"):
        raise AssetError("SKILL.md is missing YAML frontmatter")
    end = text.find("\n---", 4)
    if end < 0:
        raise AssetError("SKILL.md frontmatter is not closed")
    try:
        metadata = yaml.safe_load(text[4:end])
    except yaml.YAMLError as error:
        raise AssetError("SKILL.md frontmatter is invalid YAML") from error
    if not isinstance(metadata, dict):
        raise AssetError("SKILL.md frontmatter must be a mapping")

    name = metadata.get("name")
    description = metadata.get("description")
    if not isinstance(name, str) or not _SKILL_NAME.fullmatch(name) or len(name) > 64:
        raise AssetError("SKILL.md name is invalid")
    if not isinstance(description, str) or not description.strip():
        raise AssetError("SKILL.md description is required")
    return metadata
