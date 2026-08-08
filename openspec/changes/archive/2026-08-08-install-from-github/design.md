## Context

The repository already contains standard Python project metadata, an optional `cli` extra, and a console entry point. Those are also the inputs `uv` needs when installing directly from Git, so removing them would break both the importable-library and optional-CLI contracts.

## Goals / Non-Goals

**Goals:**

- Make the Git repository the unambiguous installation source.
- Preserve the smallest metadata surface required for Git-backed library and CLI installation.
- Keep installation examples valid for both project dependencies and one-off `uvx` execution.

**Non-Goals:**

- Add a PyPI release, publishing automation, or another distribution channel.
- Change application APIs, commands, or lifecycle behavior.

## Decisions

### Keep standard Python build metadata

Retain `pyproject.toml`, the build backend, optional dependencies, and console entry point because `uv` builds a Git dependency as a Python project. Removing packaging metadata was rejected because a repository alone does not identify imports, extras, dependencies, or executables.

### Use direct Git requirements

Documentation uses PEP 508 direct references for project installation and `uvx --from`, including `agent-router[cli]` when the command is required. Bare package names were rejected because they imply package-index resolution.

### Keep revision pinning optional

The default examples follow the repository’s default branch, while documentation permits callers to append a tag or commit for reproducibility. Mandating one fixed revision was rejected because the project has not established a release-tag policy.

## Risks / Trade-offs

- [The repository URL is unavailable or requires authentication] → Git installation reports the underlying access failure; repository visibility and credentials remain deployment concerns.
- [Default-branch installs change over time] → Callers that require reproducibility pin a tag or commit.
