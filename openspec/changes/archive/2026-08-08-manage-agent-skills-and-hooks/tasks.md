## 1. Package foundation

- [x] 1.1 Separate public core contracts, reusable utilities, and the optional CLI package.
- [x] 1.2 Add PyYAML and TomlKit runtime dependencies, optional Typer extra, and pytest/Behave development dependencies.
- [x] 1.3 Verify deterministic source loading, paths, ownership, mutation, and native document utilities through fail-first pytest TDD.

## 2. Skill lifecycle

- [x] 2.1 Implement skill loading, validation, compatibility reporting, and symlink rejection.
- [x] 2.2 Implement native user/project destination resolution, owned install reconciliation, and no-op behavior.
- [x] 2.3 Implement name-addressed uninstall that removes only intact agent-router-owned skills.

## 3. Hook lifecycle

- [x] 3.1 Implement native JSON, Kimi TOML, and Pi extension loading and scope resolution.
- [x] 3.2 Implement preserving shared-configuration reconciliation and dedicated extension projection.
- [x] 3.3 Implement explicit Claude Code/Codex portable command-hook conversion and fail-closed unsupported handling.
- [x] 3.4 Implement name-addressed uninstall that removes only intact agent-router-owned hook fragments or extensions.

## 4. Public surfaces

- [x] 4.1 Export the agent-bound Python API without importing Typer.
- [x] 4.2 Implement the six noninteractive Typer lifecycle commands, destination overrides, JSON output, and deterministic exit statuses.
- [x] 4.3 Document installation, library usage, CLI usage, scope behavior, and the native support matrix.

## 5. Verification and release readiness

- [x] 5.1 Bind every approved scenario to the real library or CLI and run the complete Behave suite to green.
- [x] 5.2 Run the complete pytest suite, package build, base-without-CLI check, CLI-extra smoke test, and strict OpenSpec validation.
