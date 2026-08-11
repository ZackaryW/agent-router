from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from agent_router.utils.destinations import Destination
from agent_router.utils.router_state import StateLocations

OwnershipState = Literal["absent", "unmanaged", "current", "outdated", "conflict"]
_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class OwnershipError(ValueError):
    """Ownership evidence is malformed or unsafe."""


@dataclass(frozen=True, slots=True)
class OwnershipRecord:
    agent: str
    kind: str
    name: str
    destination: str
    fingerprint: str
    fragment: object | None = None
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class OwnershipEvidence:
    record: OwnershipRecord | None
    locations: StateLocations
    source: Literal["none", "current", "legacy", "duplicate"]


def ownership_path(destination: Destination, kind: str, name: str) -> Path:
    root = destination.path.parent if destination.shared_config else destination.path
    return root / ".agent-router" / kind / f"{name}.json"


def serialize_ownership(record: OwnershipRecord) -> bytes:
    _validate_record(record)
    return (json.dumps(asdict(record), indent=2, sort_keys=True) + "\n").encode("utf-8")


def load_ownership(path: Path) -> OwnershipRecord | None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise OwnershipError(f"ownership record is not a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or set(value) != {
            "agent",
            "kind",
            "name",
            "destination",
            "fingerprint",
            "fragment",
            "schema_version",
        }:
            raise ValueError
        record = OwnershipRecord(**value)
        _validate_record(record)
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as error:
        raise OwnershipError(f"ownership record is invalid: {path}") from error
    return record


def load_ownership_evidence(locations: StateLocations) -> OwnershipEvidence:
    current = load_ownership(locations.current)
    legacy = load_ownership(locations.legacy)
    if current is not None and legacy is not None:
        if current != legacy:
            raise OwnershipError("current and legacy ownership records diverge")
        return OwnershipEvidence(current, locations, "duplicate")
    if current is not None:
        return OwnershipEvidence(current, locations, "current")
    if legacy is not None:
        return OwnershipEvidence(legacy, locations, "legacy")
    return OwnershipEvidence(None, locations, "none")


def classify_ownership(
    record: OwnershipRecord | None,
    *,
    agent: str,
    kind: str,
    name: str,
    destination: Path,
    content_present: bool,
    actual_fingerprint: str | None,
    expected_fingerprint: str,
) -> OwnershipState:
    if record is None:
        return "unmanaged" if content_present else "absent"
    if (
        record.agent != agent
        or record.kind != kind
        or record.name != name
        or record.destination != str(destination.resolve())
        or not content_present
        or actual_fingerprint != record.fingerprint
    ):
        return "conflict"
    return "current" if record.fingerprint == expected_fingerprint else "outdated"


def _validate_record(record: OwnershipRecord) -> None:
    if record.schema_version != 1:
        raise OwnershipError("unsupported ownership schema")
    if record.agent not in {"codex", "claude", "kimi", "pi"}:
        raise OwnershipError("invalid ownership agent")
    if record.kind not in {"skill", "hook"}:
        raise OwnershipError("invalid ownership kind")
    if not _NAME.fullmatch(record.name):
        raise OwnershipError("invalid ownership name")
    if not Path(record.destination).is_absolute():
        raise OwnershipError("ownership destination must be absolute")
    if len(record.fingerprint) != 64 or any(
        character not in "0123456789abcdef" for character in record.fingerprint
    ):
        raise OwnershipError("invalid ownership fingerprint")
