from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path, PurePath


class ArtifactPathError(ValueError):
    """A generic artifact path is absent or escapes its plugin root."""


def resolve_artifact_paths(
    plugin_root: Path, candidates: Iterable[PurePath]
) -> tuple[Path, ...]:
    root = Path(plugin_root)
    if not root.is_absolute():
        raise ArtifactPathError("plugin root must be absolute")
    try:
        canonical_root = root.resolve(strict=True)
    except OSError as error:
        raise ArtifactPathError("plugin root must be a materialized directory") from error
    if not canonical_root.is_dir():
        raise ArtifactPathError("plugin root must be a materialized directory")

    resolved: list[Path] = []
    for candidate_value in candidates:
        candidate = Path(candidate_value)
        if candidate.is_absolute():
            raise ArtifactPathError("artifact candidate must be relative")
        try:
            materialized = (canonical_root / candidate).resolve(strict=True)
        except OSError as error:
            raise ArtifactPathError(
                f"artifact candidate is not materialized: {candidate}"
            ) from error
        if not materialized.is_relative_to(canonical_root):
            raise ArtifactPathError(
                f"artifact candidate resolves outside the plugin root: {candidate}"
            )
        resolved.append(materialized)
    return tuple(resolved)
