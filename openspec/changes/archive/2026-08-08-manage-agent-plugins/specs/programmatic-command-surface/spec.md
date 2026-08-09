## ADDED Requirements

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
