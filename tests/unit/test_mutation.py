from pathlib import Path, PurePosixPath

import pytest

from agent_router.utils import mutation
from agent_router.utils.mutation import (
    DirectoryProjection,
    MutationPlan,
    RelativeWrite,
    Write,
    apply_mutation,
    atomic_write,
)


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


def test_swaps_a_completely_staged_directory_projection(tmp_path: Path) -> None:
    target = tmp_path / "reviewer"
    target.mkdir()
    (target / "stale.txt").write_bytes(b"stale")
    projection = DirectoryProjection(
        target,
        (
            RelativeWrite(PurePosixPath("SKILL.md"), b"new"),
            RelativeWrite(PurePosixPath("nested/config.json"), b"{}"),
        ),
    )

    apply_mutation(MutationPlan(writes=(), projections=(projection,)))

    assert (target / "SKILL.md").read_bytes() == b"new"
    assert (target / "nested" / "config.json").read_bytes() == b"{}"
    assert not (target / "stale.txt").exists()
    assert not tuple(tmp_path.glob(".reviewer.agent-router-*"))


def test_restores_an_overwritten_write_when_pre_swap_verification_fails(
    tmp_path: Path,
) -> None:
    target = tmp_path / "reviewer"
    target.mkdir()
    (target / "old.txt").write_bytes(b"old")
    ignore_file = tmp_path / ".gitignore"
    ignore_file.write_bytes(b"original\n")

    def fail_verification() -> None:
        raise RuntimeError("ineffective ignore")

    plan = MutationPlan(
        writes=(Write(ignore_file, b"original\n/reviewer/\n"),),
        projections=(
            DirectoryProjection(
                target, (RelativeWrite(PurePosixPath("SKILL.md"), b"new"),)
            ),
        ),
        before_projection_swap=(fail_verification,),
    )

    with pytest.raises(RuntimeError, match="ineffective"):
        apply_mutation(plan)

    assert ignore_file.read_bytes() == b"original\n"
    assert (target / "old.txt").read_bytes() == b"old"
    assert not (target / "SKILL.md").exists()


def test_removes_a_record_and_only_explicit_empty_legacy_directories(
    tmp_path: Path,
) -> None:
    router_dir = tmp_path / "native" / ".agent-router"
    kind_dir = router_dir / "skill"
    kind_dir.mkdir(parents=True)
    record = kind_dir / "reviewer.json"
    record.write_bytes(b"legacy")
    unrelated = router_dir / "keep"
    unrelated.mkdir()
    (unrelated / "other.json").write_bytes(b"keep")

    apply_mutation(
        MutationPlan(
            writes=(),
            replacements=(record,),
            prune_empty=(kind_dir, router_dir),
        )
    )

    assert not record.exists()
    assert not kind_dir.exists()
    assert (unrelated / "other.json").read_bytes() == b"keep"
    assert router_dir.exists()


def test_restores_the_old_projection_when_the_final_swap_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "reviewer"
    target.mkdir()
    (target / "old.txt").write_bytes(b"old")
    original_replace = mutation.os.replace

    def fail_prepared_swap(source, destination) -> None:
        if Path(source).name == "prepared":
            raise OSError("injected projection swap failure")
        original_replace(source, destination)

    monkeypatch.setattr(mutation.os, "replace", fail_prepared_swap)
    plan = MutationPlan(
        writes=(),
        projections=(
            DirectoryProjection(
                target, (RelativeWrite(PurePosixPath("SKILL.md"), b"new"),)
            ),
        ),
    )

    with pytest.raises(OSError, match="projection swap"):
        apply_mutation(plan)

    assert (target / "old.txt").read_bytes() == b"old"
    assert not (target / "SKILL.md").exists()
    assert not tuple(tmp_path.glob(".reviewer.agent-router-*"))


def test_restores_removed_state_when_legacy_pruning_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    router_dir = tmp_path / "native" / ".agent-router"
    kind_dir = router_dir / "skill"
    kind_dir.mkdir(parents=True)
    record = kind_dir / "reviewer.json"
    record.write_bytes(b"legacy")
    original_rmdir = Path.rmdir

    def fail_router_prune(path: Path) -> None:
        if path == router_dir:
            raise PermissionError("injected prune failure")
        original_rmdir(path)

    monkeypatch.setattr(Path, "rmdir", fail_router_prune)

    with pytest.raises(PermissionError, match="prune"):
        apply_mutation(
            MutationPlan(
                writes=(),
                replacements=(record,),
                prune_empty=(kind_dir, router_dir),
            )
        )

    assert record.read_bytes() == b"legacy"
    assert kind_dir.is_dir()
    assert router_dir.is_dir()


def test_rejects_a_symbolic_link_projection_target_before_mutation(
    tmp_path: Path,
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (real / "old.txt").write_bytes(b"old")
    target = tmp_path / "reviewer"
    target.symlink_to(real, target_is_directory=True)
    plan = MutationPlan(
        writes=(),
        projections=(
            DirectoryProjection(
                target, (RelativeWrite(PurePosixPath("SKILL.md"), b"new"),)
            ),
        ),
    )

    with pytest.raises(ValueError, match="regular directory"):
        apply_mutation(plan)

    assert target.is_symlink()
    assert (real / "old.txt").read_bytes() == b"old"
    assert not (real / "SKILL.md").exists()


def test_rejects_symbolic_link_replacement_without_exact_authorization(
    tmp_path: Path,
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    target = tmp_path / "reviewer"
    target.symlink_to(real, target_is_directory=True)

    with pytest.raises(ValueError, match="symbolic link"):
        apply_mutation(MutationPlan(writes=(), replacements=(target,)))

    assert target.is_symlink()
    assert real.is_dir()


def test_rejects_symlink_authorization_outside_replacements(tmp_path: Path) -> None:
    target = tmp_path / "reviewer"

    with pytest.raises(ValueError, match="symlink replacement authorization"):
        MutationPlan(writes=(), allowed_symlink_replacements=(target,))


def test_removes_only_an_exact_authorized_symbolic_link(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (real / "keep.txt").write_text("keep", encoding="utf-8")
    target = tmp_path / "reviewer"
    target.symlink_to(real, target_is_directory=True)

    apply_mutation(
        MutationPlan(
            writes=(),
            replacements=(target,),
            allowed_symlink_replacements=(target,),
        )
    )

    assert not target.exists()
    assert not target.is_symlink()
    assert (real / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_restores_an_authorized_symlink_when_a_later_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    target = tmp_path / "reviewer"
    target.symlink_to(real, target_is_directory=True)
    later = tmp_path / "later.txt"

    def fail_write(path: Path, content: bytes) -> None:
        raise OSError("injected write failure")

    monkeypatch.setattr(mutation, "atomic_write", fail_write)

    with pytest.raises(OSError, match="injected write failure"):
        apply_mutation(
            MutationPlan(
                writes=(Write(later, b"later"),),
                replacements=(target,),
                allowed_symlink_replacements=(target,),
            )
        )

    assert target.is_symlink()
    assert target.resolve() == real.resolve()
    assert not later.exists()


def test_rejects_a_write_inside_a_complete_projection(tmp_path: Path) -> None:
    target = tmp_path / "reviewer"
    projection = DirectoryProjection(
        target, (RelativeWrite(PurePosixPath("SKILL.md"), b"new"),)
    )

    with pytest.raises(ValueError, match="projection"):
        MutationPlan(
            writes=(Write(target / "extra.txt", b"extra"),),
            projections=(projection,),
        )


def test_cleans_staging_when_projection_preparation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "reviewer"
    target.mkdir()
    (target / "old.txt").write_bytes(b"old")

    def fail_stage(path: Path, content: bytes) -> None:
        raise OSError("injected staging failure")

    monkeypatch.setattr(mutation, "atomic_write", fail_stage)
    plan = MutationPlan(
        writes=(),
        projections=(
            DirectoryProjection(
                target, (RelativeWrite(PurePosixPath("SKILL.md"), b"new"),)
            ),
        ),
    )

    with pytest.raises(OSError, match="staging"):
        apply_mutation(plan)

    assert (target / "old.txt").read_bytes() == b"old"
    assert not tuple(tmp_path.glob(".reviewer.agent-router-*"))


def test_removes_new_auxiliary_parent_directories_during_rollback(
    tmp_path: Path,
) -> None:
    target = tmp_path / "reviewer"
    target.mkdir()
    (target / "old.txt").write_bytes(b"old")
    state_file = tmp_path / ".z-agent-router" / "ownership" / "record.json"

    def fail_verification() -> None:
        raise RuntimeError("injected verification failure")

    with pytest.raises(RuntimeError, match="verification"):
        apply_mutation(
            MutationPlan(
                writes=(Write(state_file, b"state"),),
                projections=(
                    DirectoryProjection(
                        target,
                        (RelativeWrite(PurePosixPath("SKILL.md"), b"new"),),
                    ),
                ),
                before_projection_swap=(fail_verification,),
            )
        )

    assert not (tmp_path / ".z-agent-router").exists()
    assert (target / "old.txt").read_bytes() == b"old"
