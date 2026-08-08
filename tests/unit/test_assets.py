from pathlib import Path

import pytest

from agent_router.utils.assets import (
    AssetError,
    collect_asset_tree,
    fingerprint_asset,
    parse_skill_document,
)


def test_collects_a_deterministic_regular_file_tree(tmp_path: Path) -> None:
    root = tmp_path / "reviewer"
    (root / "references").mkdir(parents=True)
    (root / "SKILL.md").write_text(
        "---\nname: reviewer\ndescription: Reviews code\n---\nBody\n",
        encoding="utf-8",
    )
    (root / "references" / "guide.md").write_bytes(b"guide")

    files = collect_asset_tree(root)

    assert [item.relative_path for item in files] == ["SKILL.md", "references/guide.md"]
    assert fingerprint_asset(files) == fingerprint_asset(reversed(files))


def test_rejects_a_symlink_inside_an_asset(tmp_path: Path) -> None:
    root = tmp_path / "reviewer"
    root.mkdir()
    target = tmp_path / "outside.txt"
    target.write_text("outside", encoding="utf-8")
    try:
        (root / "linked.txt").symlink_to(target)
    except OSError as error:
        pytest.skip(f"symbolic links unavailable: {error}")

    with pytest.raises(AssetError, match="symbolic link"):
        collect_asset_tree(root)


def test_parses_required_skill_frontmatter() -> None:
    metadata = parse_skill_document(
        b"---\nname: reviewer\ndescription: Reviews code\n---\nBody\n"
    )

    assert metadata["name"] == "reviewer"
    assert metadata["description"] == "Reviews code"


@pytest.mark.parametrize(
    "source",
    [
        b"Body only",
        b"---\nname: reviewer\n---\nBody\n",
        b"---\nname: ../reviewer\ndescription: Bad name\n---\n",
    ],
)
def test_rejects_invalid_skill_frontmatter(source: bytes) -> None:
    with pytest.raises(AssetError):
        parse_skill_document(source)
