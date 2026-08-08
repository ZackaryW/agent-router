from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tempfile


@dataclass(frozen=True, slots=True)
class Write:
    path: Path
    content: bytes


@dataclass(frozen=True, slots=True)
class MutationPlan:
    writes: tuple[Write, ...]
    replacements: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        if len({write.path for write in self.writes}) != len(self.writes):
            raise ValueError("mutation plan contains duplicate writes")
        if len(set(self.replacements)) != len(self.replacements):
            raise ValueError("mutation plan contains duplicate replacements")
        for index, path in enumerate(self.replacements):
            for other in self.replacements[index + 1 :]:
                if path in other.parents or other in path.parents:
                    raise ValueError("mutation plan contains nested replacements")


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
    staged: list[tuple[Path, Path, Path]] = []
    created_paths = tuple(
        write.path
        for write in plan.writes
        if not write.path.exists() and not write.path.is_symlink()
    )
    try:
        for path in plan.replacements:
            if not path.exists() and not path.is_symlink():
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            staging_root = Path(
                tempfile.mkdtemp(prefix=f".{path.name}.agent-router-", dir=path.parent)
            )
            backup = staging_root / "backup"
            os.replace(path, backup)
            staged.append((path, backup, staging_root))

        for write in plan.writes:
            atomic_write(write.path, write.content)
    except BaseException:
        for path in reversed(created_paths):
            _remove(path)
        for original, backup, staging_root in reversed(staged):
            _remove(original)
            os.replace(backup, original)
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
