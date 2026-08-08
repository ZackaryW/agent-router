## Why

The installation contract currently reads like `agent-router` will be resolved from a Python package index, but the settled distribution source is the project’s GitHub repository. The canonical contract must distinguish required Python build metadata from package-index publication.

## What Changes

- Establish `https://github.com/ZackaryW/agent-router` as the supported installation source for both the importable library and optional CLI.
- Require Git-backed `uv` and `uvx` examples, including the `cli` extra where the command surface is needed.
- Explicitly exclude publishing or resolving `agent-router` through PyPI or another package index.
- Retain standard Python project and build metadata so `uv` can build the repository, expose imports, resolve extras, and install the console entry point.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `programmatic-command-surface`: Define GitHub as the sole distribution source for library and CLI installation while preserving the optional CLI extra.

## Impact

- Updates the canonical programmatic command contract and installation documentation.
- Retains `pyproject.toml`, the build backend, optional dependencies, and console-script metadata without adding a package-index release workflow.
- Does not change the Python API, CLI commands, lifecycle behavior, or runtime dependencies.
