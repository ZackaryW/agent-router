## Why

Requiring Python 3.14 unnecessarily excludes users on maintained Python releases even though the implementation only depends on language and standard-library features available in Python 3.11. The declared floor should match the version the project actually supports and verifies.

## What Changes

- Lower the supported Python requirement from 3.14 to 3.11.
- Resolve project and development dependencies across the new supported range.
- Document Python 3.11 as the minimum version.
- Verify the complete library, CLI, BDD, and unit-test surfaces using Python 3.11.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `programmatic-command-surface`: Make the importable library and optional CLI installable and executable on Python 3.11 and later.

## Impact

- Updates `requires-python`, the uv lockfile, installation documentation, and compatibility behavior coverage.
- Does not add backports or compatibility dependencies because the current implementation already uses Python 3.11 as its natural standard-library floor.
- Does not change public library methods, CLI commands, or asset lifecycle behavior.
