from __future__ import annotations

import os
from pathlib import PurePath

import pytest

from agent_router.utils.artifact_paths import ArtifactPathError, resolve_artifact_paths


def test_resolve_artifact_paths_returns_canonical_absolute_materialized_paths(
    tmp_path,
) -> None:
    root = tmp_path / "plugin"
    artifact = root / "traits" / "review.yaml"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("enabled: true", encoding="utf-8")

    resolved = resolve_artifact_paths(root, (PurePath("traits/review.yaml"),))

    assert resolved == (artifact.resolve(strict=True),)
    assert resolved[0].is_absolute()


@pytest.mark.parametrize("candidate", [PurePath("/absolute"), PurePath("../outside")])
def test_resolve_artifact_paths_rejects_absolute_or_traversing_candidates(
    tmp_path, candidate
) -> None:
    root = tmp_path / "plugin"
    root.mkdir()
    (tmp_path / "outside").write_text("outside", encoding="utf-8")

    with pytest.raises(ArtifactPathError):
        resolve_artifact_paths(root, (candidate,))


def test_resolve_artifact_paths_rejects_missing_candidates(tmp_path) -> None:
    root = tmp_path / "plugin"
    root.mkdir()

    with pytest.raises(ArtifactPathError, match="materialized"):
        resolve_artifact_paths(root, (PurePath("traits/missing"),))


def test_resolve_artifact_paths_rejects_non_absolute_or_non_directory_root(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    relative = PurePath("plugin")
    (tmp_path / "plugin").mkdir()

    with pytest.raises(ArtifactPathError, match="absolute"):
        resolve_artifact_paths(relative, ())
    with pytest.raises(ArtifactPathError, match="directory"):
        resolve_artifact_paths(tmp_path / "missing", ())


def test_resolve_artifact_paths_rejects_symbolic_link_escape(tmp_path) -> None:
    root = tmp_path / "plugin"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_text("secret", encoding="utf-8")
    link = root / "linked"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symbolic links are unavailable: {error}")

    with pytest.raises(ArtifactPathError, match="outside"):
        resolve_artifact_paths(root, (PurePath("linked/secret"),))
