## ADDED Requirements

### Requirement: GitHub-only distribution
The supported distribution source for `agent-router` SHALL be `https://github.com/ZackaryW/agent-router`. Callers SHALL be able to install the base importable library or the optional `cli` extra directly from that Git repository with `uv`. Project documentation and automation SHALL NOT require or present PyPI or another Python package index as an installation source. The repository SHALL retain the Python project metadata needed for Git-based builds, imports, optional extras, and console entry points.

#### Scenario: Install the library from GitHub
- **WHEN** a caller adds `agent-router` using the supported Git repository URL without the `cli` extra
- **THEN** `uv` builds the repository and installs the importable base library without requiring a package-index release of `agent-router`

#### Scenario: Install the CLI extra from GitHub
- **WHEN** a caller adds `agent-router[cli]` using the supported Git repository URL
- **THEN** `uv` builds the repository with its optional CLI dependencies and exposes the `agent-router` command

#### Scenario: Avoid package-index installation guidance
- **WHEN** a caller consults the supported installation documentation
- **THEN** every `agent-router` installation source points to the GitHub repository rather than PyPI or another Python package index

## MODIFIED Requirements

### Requirement: Optional packaged uvx command
The GitHub repository with the `agent_router[cli]` extra SHALL provide the Typer-based `agent-router` console command for execution through `uvx` without requiring a package-index release. The command SHALL expose `skill inspect`, `skill install`, `skill uninstall`, `hook inspect`, `hook install`, and `hook uninstall`. Every invocation SHALL accept exactly one `--agent`. Install commands SHALL expose `--allow-conversion`, disabled by default, as explicit authorization to use an available converter for that operation. The command SHALL NOT require the selected agent's executable to be installed because it manages filesystem projections rather than launching the agent.

#### Scenario: Invoke through uvx
- **WHEN** a caller runs the `agent-router` command through `uvx` with the `cli` extra sourced from `https://github.com/ZackaryW/agent-router`
- **THEN** the command performs the requested valid skill or hook operation without resolving `agent-router` from a package index

#### Scenario: Authorize conversion through the command
- **WHEN** a caller supplies `--allow-conversion` for a non-native asset with an available explicit converter
- **THEN** the command may validate and use that converter for the selected agent and operation

#### Scenario: Keep CLI dependencies isolated
- **WHEN** the optional CLI package imports the library lifecycle
- **THEN** CLI dependencies remain confined to the CLI package and no core or utility module imports them

#### Scenario: Prepare assets before installing an agent executable
- **WHEN** a valid lifecycle request selects an agent whose executable is absent
- **THEN** the command performs the filesystem lifecycle without rejecting the request for that absence

#### Scenario: Reject multiple command agents
- **WHEN** a caller supplies more than one agent to one command invocation
- **THEN** the command rejects the request before destination mutation
