## ADDED Requirements

### Requirement: Python 3.11 compatibility
The base `agent_router` library and optional `cli` extra SHALL support CPython 3.11 and every later Python version permitted by project dependency resolution. Project metadata SHALL declare Python 3.11 as the minimum supported version, and the complete public library and command behavior SHALL execute on Python 3.11 without compatibility packages that are unnecessary on that version.

#### Scenario: Install the base library on Python 3.11
- **WHEN** a caller installs the base library from the supported Git repository into a Python 3.11 environment
- **THEN** dependency resolution and import of the supported public library contracts succeed

#### Scenario: Run the CLI on Python 3.11
- **WHEN** a caller installs the `cli` extra from the supported Git repository into a Python 3.11 environment
- **THEN** the `agent-router` command and its supported lifecycle operations execute successfully

#### Scenario: Reject an older runtime
- **WHEN** an installer evaluates the project for a Python version older than 3.11
- **THEN** project metadata reports that the runtime is below the supported Python floor
