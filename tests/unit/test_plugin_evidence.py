from __future__ import annotations

import json

import pytest

from agent_router.utils.plugin_evidence import (
    NativePluginDecodeError,
    decode_claude_plugins,
    decode_codex_plugins,
    decode_kimi_plugins,
    decode_pi_packages,
)


def test_decode_codex_preserves_installed_and_available_evidence(tmp_path) -> None:
    root = tmp_path / "installed"
    payload = json.dumps(
        {
            "installed": [
                {
                    "pluginId": "docs@internal",
                    "name": "docs",
                    "marketplaceName": "internal",
                    "version": "1.2",
                    "installed": True,
                    "enabled": False,
                    "source": {"source": "local", "path": str(root)},
                }
            ],
            "available": [
                {
                    "pluginId": "lint@internal",
                    "name": "lint",
                    "marketplaceName": "internal",
                    "version": "2.0",
                    "installed": False,
                    "enabled": False,
                    "source": {"source": "git", "url": "https://example.test/lint"},
                }
            ],
        }
    )

    installed, available = decode_codex_plugins(payload)

    assert installed.native_ref == "docs@internal"
    assert installed.scope == "user"
    assert installed.source == "internal"
    assert installed.installed_version == "1.2"
    assert installed.activation == "disabled"
    assert installed.runtime_root == root
    assert available.native_ref == "lint@internal"
    assert available.installed is False
    assert available.available_version == "2.0"
    assert available.runtime_root is None


def test_decode_claude_preserves_exact_scope_and_root(tmp_path) -> None:
    root = tmp_path / "cache" / "review" / "4"
    payload = json.dumps(
        [
            {
                "id": "review@team",
                "version": "4.0",
                "scope": "local",
                "enabled": True,
                "installPath": str(root),
                "installedAt": "2026-08-08T00:00:00Z",
            }
        ]
    )

    (record,) = decode_claude_plugins(payload)

    assert record.native_ref == "review@team"
    assert record.name == "review"
    assert record.source == "team"
    assert record.scope == "local"
    assert record.installed_version == "4.0"
    assert record.activation == "enabled"
    assert record.runtime_root == root


def test_decode_kimi_reads_documented_installed_state(tmp_path) -> None:
    root = tmp_path / "plugins" / "managed" / "finance"
    installed = tmp_path / "plugins" / "installed.json"
    installed.parent.mkdir(parents=True)
    installed.write_text(
        json.dumps(
            {
                "version": 1,
                "plugins": [
                    {
                        "id": "finance",
                        "root": str(root),
                        "source": "github",
                        "enabled": False,
                        "installedAt": "2026-08-08T00:00:00Z",
                        "originalSource": "https://github.com/example/finance",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    (record,) = decode_kimi_plugins(tmp_path)

    assert record.native_ref == "finance"
    assert record.scope == "user"
    assert record.source == "https://github.com/example/finance"
    assert record.activation == "disabled"
    assert record.runtime_root == root


def test_decode_pi_preserves_user_and_project_package_roots(tmp_path) -> None:
    user_root = tmp_path / "user-package"
    project_root = tmp_path / "project-package"
    payload = (
        "User packages:\n"
        "  npm:pi-tools\n"
        f"    {user_root}\n"
        "Project packages:\n"
        "  git:https://example.test/team.git\n"
        f"    {project_root}\n"
    )

    user, project = decode_pi_packages(payload)

    assert (user.native_ref, user.scope, user.runtime_root) == (
        "npm:pi-tools",
        "user",
        user_root,
    )
    assert (project.native_ref, project.scope, project.runtime_root) == (
        "git:https://example.test/team.git",
        "project",
        project_root,
    )
    assert user.activation == project.activation == "partial"


@pytest.mark.parametrize(
    ("decoder", "payload"),
    [
        (decode_codex_plugins, "[]"),
        (decode_claude_plugins, '{"plugins": []}'),
        (decode_pi_packages, "npm:missing-section"),
    ],
)
def test_command_decoders_reject_unrecognized_shapes(decoder, payload) -> None:
    with pytest.raises(NativePluginDecodeError):
        decoder(payload)


def test_kimi_decoder_rejects_malformed_state_without_cache_fallback(tmp_path) -> None:
    installed = tmp_path / "plugins" / "installed.json"
    installed.parent.mkdir(parents=True)
    installed.write_text('{"version": 2, "plugins": []}', encoding="utf-8")

    with pytest.raises(NativePluginDecodeError):
        decode_kimi_plugins(tmp_path)
