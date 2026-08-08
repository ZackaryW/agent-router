from pathlib import Path

import pytest

from agent_router.utils.destinations import Destination
from agent_router.utils.ownership import (
    OwnershipError,
    OwnershipRecord,
    classify_ownership,
    load_ownership,
    ownership_path,
    serialize_ownership,
)


def record_for(path: Path, fingerprint: str = "a" * 64) -> OwnershipRecord:
    return OwnershipRecord(
        agent="codex",
        kind="skill",
        name="reviewer",
        destination=str(path.resolve()),
        fingerprint=fingerprint,
    )


def test_places_ownership_outside_copied_content(tmp_path: Path) -> None:
    container = Destination(tmp_path / "skills", shared_config=False)
    shared = Destination(tmp_path / "settings.json", shared_config=True)

    assert ownership_path(container, "skill", "reviewer") == (
        tmp_path / "skills" / ".agent-router" / "skill" / "reviewer.json"
    )
    assert ownership_path(shared, "hook", "reviewer") == (
        tmp_path / ".agent-router" / "hook" / "reviewer.json"
    )


def test_round_trips_a_strict_ownership_record(tmp_path: Path) -> None:
    path = tmp_path / "skills"
    manifest = tmp_path / "record.json"
    manifest.write_bytes(serialize_ownership(record_for(path)))

    assert load_ownership(manifest) == record_for(path)


def test_rejects_an_invalid_ownership_record(tmp_path: Path) -> None:
    manifest = tmp_path / "record.json"
    manifest.write_text('{"schema_version": 1, "agent": "codex"}', encoding="utf-8")

    with pytest.raises(OwnershipError, match="invalid"):
        load_ownership(manifest)


@pytest.mark.parametrize(
    ("record", "present", "actual", "expected", "state"),
    [
        (None, False, None, "a" * 64, "absent"),
        (None, True, "a" * 64, "a" * 64, "unmanaged"),
        ("record", True, "a" * 64, "a" * 64, "current"),
        ("record", True, "a" * 64, "b" * 64, "outdated"),
        ("record", True, "b" * 64, "a" * 64, "conflict"),
        ("record", False, None, "a" * 64, "conflict"),
    ],
)
def test_classifies_projection_ownership(
    tmp_path: Path,
    record: str | None,
    present: bool,
    actual: str | None,
    expected: str,
    state: str,
) -> None:
    destination = tmp_path / "skills"

    result = classify_ownership(
        record_for(destination) if record else None,
        agent="codex",
        kind="skill",
        name="reviewer",
        destination=destination,
        content_present=present,
        actual_fingerprint=actual,
        expected_fingerprint=expected,
    )

    assert result == state


def test_rejects_a_record_copied_to_another_destination(tmp_path: Path) -> None:
    result = classify_ownership(
        record_for(tmp_path / "original"),
        agent="codex",
        kind="skill",
        name="reviewer",
        destination=tmp_path / "copy",
        content_present=True,
        actual_fingerprint="a" * 64,
        expected_fingerprint="a" * 64,
    )

    assert result == "conflict"
