from pathlib import Path

import pytest

from agent_router.utils import mutation
from agent_router.utils.mutation import MutationPlan, Write, apply_mutation, atomic_write


def test_atomically_replaces_file_content(tmp_path: Path) -> None:
    destination = tmp_path / "settings.json"
    destination.write_bytes(b"old")

    atomic_write(destination, b"new")

    assert destination.read_bytes() == b"new"


def test_applies_a_directory_replacement(tmp_path: Path) -> None:
    destination = tmp_path / "reviewer"
    destination.mkdir()
    (destination / "old.txt").write_bytes(b"old")
    plan = MutationPlan(
        writes=(Write(destination / "SKILL.md", b"new"),),
        replacements=(destination,),
    )

    apply_mutation(plan)

    assert not (destination / "old.txt").exists()
    assert (destination / "SKILL.md").read_bytes() == b"new"


def test_restores_staged_content_when_a_later_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "reviewer"
    destination.mkdir()
    (destination / "old.txt").write_bytes(b"old")
    other = tmp_path / "other.txt"
    original = mutation.atomic_write
    calls = 0

    def fail_second(path: Path, content: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected failure")
        original(path, content)

    monkeypatch.setattr(mutation, "atomic_write", fail_second)
    plan = MutationPlan(
        writes=(
            Write(destination / "SKILL.md", b"new"),
            Write(other, b"partial"),
        ),
        replacements=(destination,),
    )

    with pytest.raises(OSError, match="injected failure"):
        apply_mutation(plan)

    assert (destination / "old.txt").read_bytes() == b"old"
    assert not (destination / "SKILL.md").exists()
    assert not other.exists()


def test_rejects_nested_replacement_ownership(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    child = parent / "child"

    with pytest.raises(ValueError, match="nested"):
        MutationPlan(writes=(), replacements=(parent, child))
