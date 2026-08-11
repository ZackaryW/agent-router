# Router State Storage Specification

## Purpose

Defines collision-safe router-owned persistent state outside native agent discovery surfaces, including scoped storage and safe migration from legacy relative state.

## Requirements

### Requirement: Scope router-owned persistent state outside native agent surfaces
The system SHALL store user-scope ownership receipts, plugin receipts, and artifact-policy overrides beneath `~/.z-agent-router`. It SHALL store project-scope router-owned state beneath `<project>/.z-agent-router` for the explicitly selected project root. Persistent router state SHALL NOT be created beneath a native agent skill, hook, extension, configuration, registry, cache, or runtime discovery surface.

An explicit isolated `AgentEnvironment` SHALL resolve router-owned plugin state beneath that environment rather than reading or writing the default user root. A custom asset destination SHALL change the addressed native projection without moving state away from the root selected by semantic scope.

#### Scenario: Store user state outside an agent surface
- **WHEN** a user-scope lifecycle operation records router ownership
- **THEN** the record is stored beneath `~/.z-agent-router` and no `.agent-router` directory is created beneath the selected agent's native destination

#### Scenario: Store project state with the selected project
- **WHEN** a project-scope lifecycle operation records router ownership for an explicit project root
- **THEN** the record is stored beneath that project's `.z-agent-router` root and outside every native agent destination

#### Scenario: Retain scoped state for a custom destination
- **WHEN** a caller supplies an explicit asset destination in user or project scope
- **THEN** the system addresses that projection while retaining router state beneath the selected semantic scope's state root

#### Scenario: Isolate an explicit plugin environment
- **WHEN** plugin lifecycle receives an explicit isolated `AgentEnvironment`
- **THEN** native adapter state and router-owned receipts and policies use only that environment and do not read or write default user state

### Requirement: Bind state records to exact projection identity
The system SHALL distinguish persistent records by selected agent, asset kind, stable asset identity, and canonical native destination so identically named assets in different agents, projects, scopes, or explicit destinations do not claim one another. A record resolved through a state key SHALL still validate its complete stored identity before authorizing mutation.

#### Scenario: Keep same-named project skills independent
- **WHEN** two projects contain same-named managed skills for the same agent
- **THEN** each project resolves and validates only its own ownership record

#### Scenario: Reject displaced state evidence
- **WHEN** a state record is copied or resolved for a different agent, asset, or canonical destination
- **THEN** the system reports conflicting ownership without mutating either projection

### Requirement: Migrate legacy relative router state safely
Inspection SHALL read a valid legacy `.agent-router` record at its previously supported location when no current scoped record exists, without mutating either state location. The next authorized lifecycle mutation SHALL publish equivalent current state beneath the selected `.z-agent-router` root and remove the proven legacy record as part of the same recoverable operation. The system SHALL remove only router-owned legacy directories proven empty after their records are removed.

Malformed legacy evidence, divergent current and legacy records, or legacy evidence that does not validate the addressed projection SHALL remain a conflict. Receipt decoding SHALL remain independent of the current packaged asset inventory and runtime location so intact historical state can authorize migration.

#### Scenario: Inspect valid legacy ownership without mutation
- **WHEN** current scoped state is absent and a valid legacy record proves the addressed intact projection
- **THEN** inspection reports the projection from that evidence without creating, changing, or deleting state

#### Scenario: Migrate on an authorized mutation
- **WHEN** an install, update, or uninstall operation is authorized by valid legacy evidence
- **THEN** the operation publishes or consumes current scoped state, removes the migrated legacy record, and leaves no proven-empty legacy router directory in the native surface

#### Scenario: Reject divergent duplicate evidence
- **WHEN** current and legacy records both exist but do not describe identical ownership evidence
- **THEN** the operation reports a conflict without changing either record or the native projection

#### Scenario: Roll back failed migration
- **WHEN** any native projection, current state, or legacy cleanup step fails during migration
- **THEN** the system restores the pre-operation projection and state evidence rather than reporting successful migration
