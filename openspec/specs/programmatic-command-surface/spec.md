# Programmatic Command Surface Specification

## Purpose

Exposes the agent asset lifecycle through an importable base library and an optional deterministic command suitable for direct human use and unattended automation through `uvx`.

## Requirements

### Requirement: Importable base library
The base `agent_router` installation SHALL expose the supported agent asset lifecycle as an importable Python library without requiring Typer or another CLI-only dependency. Importing the library SHALL NOT import the CLI package transitively. Attempting to invoke or import the optional command surface without the `cli` extra SHALL report that `agent_router[cli]` is required rather than exposing a raw optional-dependency import failure.

#### Scenario: Import without CLI dependencies
- **WHEN** a Python environment installs the base package without the `cli` extra
- **THEN** importing `agent_router` and its supported library contracts succeeds without Typer being installed

#### Scenario: Invoke an unavailable optional command
- **WHEN** a caller invokes the command surface from a base-only installation
- **THEN** the system reports an actionable instruction to install `agent_router[cli]`

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

### Requirement: Agent-bound Python lifecycle
The supported Python API SHALL expose `Agent`, `AgentRouter`, `Skill`, `Hook`, `HookTransition`, `Scope`, structured compatibility and lifecycle results, and typed domain errors. Constructing `AgentRouter` with one `Agent` SHALL bind subsequent lifecycle operations to that agent without performing filesystem mutation during construction.

`Skill.from_path` and `Hook.from_path` SHALL load and validate one existing local source asset without mutating an agent destination and SHALL make detected native-agent compatibility available to library callers. Agent-bound skill and hook inspection, installation, and uninstallation SHALL be available through Pythonic methods. Each lifecycle method SHALL use user scope by default, require an explicit `project_root` for project scope, and accept an optional `destination` override with the same behavior and safety contract as the CLI `--destination` option. Installation SHALL accept `allow_conversion`, which SHALL default to false. Hook inspection and installation SHALL accept an immutable sequence of exact predecessor `Hook` assets, defaulting to empty. Uninstallation SHALL accept a stable asset name and SHALL NOT require the original source. Methods SHALL return structured results or raise typed domain errors rather than terminating the process.

Lifecycle results SHALL expose a nullable hook transition independently of the existing `converted` flag. The transition SHALL distinguish exact predecessor replacement, predecessor pruning beside a current hook, restoration of a wholly missing owned hook, and removal of stale ownership for a wholly absent hook. The `converted` flag SHALL retain only its existing cross-agent source-conversion meaning.

#### Scenario: Install through the library
- **WHEN** a caller invokes `AgentRouter(Agent.CODEX).install_skill(Skill.from_path(source))`
- **THEN** the library performs the Codex-bound managed installation and returns a structured lifecycle result

#### Scenario: Inspect compatibility before installation
- **WHEN** a caller loads a valid source through `Skill.from_path` or `Hook.from_path`
- **THEN** the library returns an asset whose detected native-agent compatibility can be inspected without constructing a router or mutating a destination

#### Scenario: Supply predecessors through the library
- **WHEN** a caller supplies validated predecessor hooks to hook inspection or installation
- **THEN** the library evaluates only those exact assets for the selected destination and returns structured transition evidence without changing conversion semantics

#### Scenario: Authorize conversion through the library
- **WHEN** a caller passes `allow_conversion=True` for a non-native asset with an available explicit converter
- **THEN** the library may validate and use that converter for the selected agent and operation

#### Scenario: Override a library destination
- **WHEN** a caller passes `destination` to an agent-bound `install_skill` invocation
- **THEN** the library uses that explicit destination under the same validation, ownership, and mutation rules as the CLI override

#### Scenario: Inspect a library destination
- **WHEN** a caller passes `destination` to an agent-bound skill or hook inspection
- **THEN** the library reports compatibility and relevant state at that exact destination without mutation

#### Scenario: Uninstall from a library destination
- **WHEN** a caller passes an asset name and `destination` to an agent-bound uninstallation method
- **THEN** the library removes only an intact projection installed and owned by `agent-router` at that destination or its stale ownership evidence when the owned projection is proven wholly absent

#### Scenario: Select a library project scope
- **WHEN** a caller passes `Scope.PROJECT` and an explicit `project_root` to an agent-bound lifecycle operation
- **THEN** the library resolves the selected agent's native repository-local destination from that project root

#### Scenario: Retain project semantics with a library destination
- **WHEN** a caller selects `Scope.PROJECT` and supplies `destination` without `project_root`
- **THEN** the library rejects the request before destination inspection or mutation

#### Scenario: Report a library domain conflict
- **WHEN** a library lifecycle operation encounters expected conflicting managed state
- **THEN** it raises a typed domain error without printing CLI output or terminating the Python process

### Requirement: Optional packaged uvx command
The GitHub repository with the `agent_router[cli]` extra SHALL provide the Typer-based `agent-router` console command for execution through `uvx` without requiring a package-index release. The command SHALL expose `skill inspect`, `skill install`, `skill uninstall`, `hook inspect`, `hook install`, and `hook uninstall`. Every invocation SHALL accept exactly one `--agent`. Install commands SHALL expose `--allow-conversion`, disabled by default, as explicit authorization to use an available converter for that operation. Hook inspect and install SHALL accept repeatable explicit `--predecessor` source paths and SHALL load each through the same hook source validation as the library. The command SHALL NOT require the selected agent's executable to be installed because it manages filesystem projections rather than launching the agent.

#### Scenario: Invoke through uvx
- **WHEN** a caller runs the `agent-router` command through `uvx` with the `cli` extra sourced from `https://github.com/ZackaryW/agent-router`
- **THEN** the command performs the requested valid skill or hook operation without resolving `agent-router` from a package index

#### Scenario: Authorize conversion through the command
- **WHEN** a caller supplies `--allow-conversion` for a non-native asset with an available explicit converter
- **THEN** the command may validate and use that converter for the selected agent and operation

#### Scenario: Supply hook predecessors through the command
- **WHEN** a caller supplies one or more `--predecessor` paths to hook inspect or install
- **THEN** the command validates and supplies only those exact hook assets to the selected lifecycle operation

#### Scenario: Keep CLI dependencies isolated
- **WHEN** the optional CLI package imports the library lifecycle
- **THEN** CLI dependencies remain confined to the CLI package and no core or utility module imports them

#### Scenario: Prepare assets before installing an agent executable
- **WHEN** a valid lifecycle request selects an agent whose executable is absent
- **THEN** the command performs the filesystem lifecycle without rejecting the request for that absence

#### Scenario: Reject multiple command agents
- **WHEN** a caller supplies more than one agent to one command invocation
- **THEN** the command rejects the request before destination mutation

### Requirement: Explicit noninteractive operation
Programmatic lifecycle operations SHALL accept explicit agent selection, optional scope selection, any required project root, and all other outcome-changing inputs without requiring an interactive selector or confirmation prompt. Uninstalling an owned asset through the explicit uninstall operation SHALL NOT add a confirmation prompt.

#### Scenario: Run without a terminal
- **WHEN** a caller provides a complete valid request in a noninteractive environment
- **THEN** the system completes or rejects the operation without waiting for user input

### Requirement: Explicit command scope
The command SHALL expose user-global and repository-local lifecycle scopes through `--scope`, defaulting to `user`. A repository-local request SHALL require `--project-root` even when `--destination` is supplied and SHALL resolve native semantics from that root without depending on the process working directory. An unsupported agent, asset, and scope combination SHALL fail deterministically before mutation.

#### Scenario: Use the default command scope
- **WHEN** a caller omits `--scope` from an otherwise valid command
- **THEN** the command operates in user-global scope

#### Scenario: Select a project scope through the command
- **WHEN** a caller supplies `--scope project --project-root <path>` for a natively supported project asset surface
- **THEN** the command operates on the destination resolved for that agent beneath the supplied repository root

#### Scenario: Omit a required project root
- **WHEN** a caller selects project scope without `--project-root`
- **THEN** the command rejects the request as invalid before destination inspection or mutation

### Requirement: Explicit installation destination
Skill and hook inspection, installation, and uninstallation commands SHALL accept a `--destination` path that replaces the selected agent adapter's normally resolved physical destination for that invocation without changing its semantic scope. The overridden destination SHALL remain subject to the same validation, conflict detection, ownership tracking, idempotence, and mutation-safety requirements as a default destination.

#### Scenario: Install into a custom destination
- **WHEN** a caller supplies a valid `--destination` path with an otherwise valid installation request
- **THEN** the system plans and applies the managed installation at that path instead of the selected agent's default destination

#### Scenario: Reject a conflicting custom destination
- **WHEN** the supplied `--destination` contains unmanaged or modified state that conflicts with the intended installation
- **THEN** the system rejects the installation without overwriting the conflicting content

#### Scenario: Inspect a custom destination
- **WHEN** a caller supplies `--destination` to an inspect command
- **THEN** the system reports compatibility and relevant state at that exact destination without mutation

#### Scenario: Uninstall from a custom destination
- **WHEN** a caller supplies an asset name and `--destination` to an uninstall command
- **THEN** the system removes only an intact projection installed and owned by `agent-router` at that destination

### Requirement: Deterministic process outcome
The command SHALL emit human-readable output by default and a stable JSON result envelope when `--json` is supplied. Results SHALL be written to standard output, diagnostics SHALL be written to standard error, and expected domain errors SHALL NOT expose implementation tracebacks. The command SHALL exit with status `0` for success or an already-converged no-op, `2` for invalid or unsupported requests, `3` for ownership or destination conflicts, and `1` for unexpected operational failures.

#### Scenario: Report a managed-state conflict
- **WHEN** an operation detects an unmanaged or modified destination conflict
- **THEN** the command exits with status `3` and identifies the selected agent and conflicting destination without changing the affected destination

#### Scenario: Emit a JSON result
- **WHEN** a caller supplies `--json` to a lifecycle command
- **THEN** the command writes one stable structured result envelope to standard output and keeps diagnostics on standard error

### Requirement: Programmatic plugin management surface
The importable library SHALL expose agent-bound plugin discovery, generic-artifact registration, policy, status, and resolution, installation, update, and removal without importing CLI-only dependencies. The optional CLI SHALL expose `plugin discover`, `plugin install`, `plugin update`, `plugin remove`, `plugin artifact status`, and `plugin artifact set` commands with exactly one explicit `--agent`. `plugin discover` SHALL default to installed records and accept `--available` for configured native catalog entries. Lifecycle commands SHALL accept exact native scope when applicable, and direct-source install SHALL accept explicit `--trust`. Discovery and artifact-status output SHALL include native activation evidence and canonical absolute runtime or artifact paths when materialized. Both surfaces SHALL return or emit the normalized plugin records, artifact statuses, and lifecycle outcomes owned by the plugin capabilities.

#### Scenario: Discover through the library
- **WHEN** a caller requests plugin discovery from an agent-bound router
- **THEN** the library returns structured native plugin records, activation evidence, and canonical absolute materialized roots without CLI output or process termination

#### Scenario: Resolve artifacts through a thin extension
- **WHEN** a caller registers a namespaced artifact convention and resolves it through an agent-bound router
- **THEN** the library returns canonical absolute artifact paths and immutable plugin contexts without importing CLI dependencies or interpreting artifact-specific content

#### Scenario: Query and set artifact policy
- **WHEN** a caller queries artifact status or sets `inherit`, `enabled`, or `disabled` for one scoped plugin reference and registered artifact identifier
- **THEN** the library or CLI returns the effective status and reason without changing native plugin enablement

#### Scenario: Install through the command
- **WHEN** a caller invokes `plugin install` with a valid native reference and exactly one agent
- **THEN** the command performs that agent-bound installation and emits the deterministic lifecycle outcome

#### Scenario: Update through the command
- **WHEN** a caller invokes `plugin update` with a valid installed native reference and exactly one agent
- **THEN** the command updates only the selected plugin or reports an already-current no-op

#### Scenario: Remove through the command
- **WHEN** a caller invokes `plugin remove` with a valid installed native reference and exactly one agent
- **THEN** the command removes only the selected plugin installation and emits the deterministic lifecycle outcome

#### Scenario: Keep plugin management optional
- **WHEN** the base library is imported without the `cli` extra
- **THEN** plugin discovery and lifecycle library contracts remain importable without Typer

### Requirement: Selectable complete adapter state root
Every plugin and artifact-policy command SHALL accept `--destination`, and the library SHALL expose an equivalent immutable `AgentEnvironment` contract. When selected, that path SHALL be the complete isolated state root for the invoked adapter and router-owned receipts and artifact-policy overrides. The selected adapter SHALL derive all native registry, cache, runtime, and policy paths through that environment and SHALL neither read nor write the default agent or router state roots. `--destination` SHALL NOT be interpreted as a forced plugin runtime directory outside the selected native adapter layout.

#### Scenario: Isolate command state
- **WHEN** a plugin command receives an explicit destination
- **THEN** native adapter state and router-owned receipts and artifact policies resolve only through that isolated root while default user state remains untouched

#### Scenario: Isolate library state
- **WHEN** an agent-bound router receives an explicit `AgentEnvironment`
- **THEN** discovery, lifecycle, and artifact operations use that environment without importing or depending on CLI code
