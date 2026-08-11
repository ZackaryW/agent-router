from __future__ import annotations

import errno
import os
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True, slots=True)
class Write:
    path: Path
    content: bytes


@dataclass(frozen=True, slots=True)
class RelativeWrite:
    path: PurePosixPath
    content: bytes

    def __post_init__(self) -> None:
        path = PurePosixPath(self.path)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise ValueError("projection write path must stay relative to its target")
        object.__setattr__(self, "path", path)


@dataclass(frozen=True, slots=True)
class DirectoryProjection:
    target: Path
    files: tuple[RelativeWrite, ...]

    def __post_init__(self) -> None:
        if not self.files:
            raise ValueError("directory projection must contain files")
        if len({item.path for item in self.files}) != len(self.files):
            raise ValueError("directory projection contains duplicate writes")


Verification = Callable[[], None]


@dataclass(frozen=True, slots=True)
class MutationPlan:
    writes: tuple[Write, ...]
    replacements: tuple[Path, ...] = ()
    projections: tuple[DirectoryProjection, ...] = ()
    prune_empty: tuple[Path, ...] = ()
    before_projection_swap: tuple[Verification, ...] = ()

    def __post_init__(self) -> None:
        if len({write.path for write in self.writes}) != len(self.writes):
            raise ValueError("mutation plan contains duplicate writes")
        if len(set(self.replacements)) != len(self.replacements):
            raise ValueError("mutation plan contains duplicate replacements")
        if len({item.target for item in self.projections}) != len(self.projections):
            raise ValueError("mutation plan contains duplicate projections")
        for index, path in enumerate(self.replacements):
            for other in self.replacements[index + 1 :]:
                if path in other.parents or other in path.parents:
                    raise ValueError("mutation plan contains nested replacements")
        for index, projection in enumerate(self.projections):
            other_roles = (
                *(write.path for write in self.writes),
                *self.replacements,
                *(item.target for item in self.projections[index + 1 :]),
            )
            if any(_paths_overlap(projection.target, path) for path in other_roles):
                raise ValueError("mutation plan contains overlapping projection roles")


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def apply_mutation(plan: MutationPlan) -> None:
    _validate_filesystem_roles(plan)
    staged: list[tuple[Path, Path, Path]] = []
    projections: list[tuple[DirectoryProjection, Path, Path]] = []
    pruned: list[Path] = []
    created_directories = _missing_parent_directories(plan.writes)
    created_paths = tuple(
        write.path
        for write in plan.writes
        if not write.path.exists() and not write.path.is_symlink()
    )
    try:
        for projection in plan.projections:
            projection.target.parent.mkdir(parents=True, exist_ok=True)
            staging_root = Path(
                tempfile.mkdtemp(
                    prefix=f".{projection.target.name}.agent-router-",
                    dir=projection.target.parent,
                )
            )
            prepared = staging_root / "prepared"
            prepared.mkdir()
            projections.append((projection, prepared, staging_root))
            for write in projection.files:
                atomic_write(
                    prepared.joinpath(*write.path.parts),
                    write.content,
                )

        for path in plan.replacements:
            if not path.exists() and not path.is_symlink():
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            staging_parent = _backup_parent(path, plan.prune_empty)
            staging_root = Path(
                tempfile.mkdtemp(
                    prefix=f".{path.name}.agent-router-", dir=staging_parent
                )
            )
            backup = staging_root / "backup"
            os.replace(path, backup)
            staged.append((path, backup, staging_root))

        for write in plan.writes:
            if write.path.exists() or write.path.is_symlink():
                write.path.parent.mkdir(parents=True, exist_ok=True)
                staging_parent = _backup_parent(write.path, plan.prune_empty)
                staging_root = Path(
                    tempfile.mkdtemp(
                        prefix=f".{write.path.name}.agent-router-",
                        dir=staging_parent,
                    )
                )
                backup = staging_root / "backup"
                os.replace(write.path, backup)
                staged.append((write.path, backup, staging_root))
            atomic_write(write.path, write.content)

        for verification in plan.before_projection_swap:
            verification()

        for projection, prepared, staging_root in projections:
            backup = staging_root / "backup"
            os.replace(projection.target, backup)
            staged.append((projection.target, backup, staging_root))
            os.replace(prepared, projection.target)

        for path in plan.prune_empty:
            if not path.exists() and not path.is_symlink():
                continue
            try:
                path.rmdir()
            except OSError as error:
                if error.errno not in {errno.ENOTEMPTY, errno.EEXIST}:
                    raise
            else:
                pruned.append(path)
    except BaseException:
        for path in reversed(pruned):
            path.mkdir(parents=True, exist_ok=True)
        for path in reversed(created_paths):
            _remove(path)
        for original, backup, staging_root in reversed(staged):
            _remove(original)
            original.parent.mkdir(parents=True, exist_ok=True)
            os.replace(backup, original)
            _remove(staging_root)
        for path in sorted(
            created_directories, key=lambda item: len(item.parts), reverse=True
        ):
            try:
                path.rmdir()
            except OSError as error:
                if error.errno not in {errno.ENOENT, errno.ENOTEMPTY, errno.EEXIST}:
                    raise
        for _, _, staging_root in projections:
            _remove(staging_root)
        raise
    else:
        for _, _, staging_root in staged:
            _remove(staging_root)


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def _backup_parent(path: Path, prune_empty: tuple[Path, ...]) -> Path:
    parent = path.parent
    while any(parent == pruned or pruned in parent.parents for pruned in prune_empty):
        parent = parent.parent
    parent.mkdir(parents=True, exist_ok=True)
    return parent


def _validate_filesystem_roles(plan: MutationPlan) -> None:
    for projection in plan.projections:
        if projection.target.is_symlink() or not projection.target.is_dir():
            raise ValueError("projection target must be an existing regular directory")
    for path in (*plan.replacements, *(write.path for write in plan.writes)):
        if path.is_symlink():
            raise ValueError("mutation path must not be a symbolic link")
    for path in plan.prune_empty:
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise ValueError("prune path must be a regular directory")


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _missing_parent_directories(writes: tuple[Write, ...]) -> set[Path]:
    missing: set[Path] = set()
    for write in writes:
        parent = write.path.parent
        while not parent.exists() and not parent.is_symlink():
            missing.add(parent)
            parent = parent.parent
    return missing
