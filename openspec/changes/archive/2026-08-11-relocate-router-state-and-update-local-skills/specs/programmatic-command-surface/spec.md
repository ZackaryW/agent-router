## ADDED Requirements

### Requirement: Explicit project skill update surface
The importable library SHALL expose an agent-bound `update_skill` method, and the optional CLI SHALL expose `skill update`. Both surfaces SHALL require project scope and an explicit project root, accept the same validated skill source and optional destination override as skill installation, and invoke the authoritative complete-target update contract rather than uninstalling and reinstalling through separate public operations.

Both surfaces SHALL accept `exact`, `pattern`, or `none` Git-ignore policy. Exact SHALL be the default. Pattern SHALL require one explicit pattern value, and none SHALL disable Git-ignore inspection and mutation. The library SHALL expose these choices as a validated public contract rather than untyped implementation flags. The command SHALL remain noninteractive and SHALL support the existing human-readable and JSON lifecycle result forms.

#### Scenario: Update a project skill through the library
- **WHEN** a caller invokes `AgentRouter(...).update_skill(...)` with project scope, an explicit project root, and valid update input
- **THEN** the library replaces or reports a no-op for only the resolved target and returns a structured lifecycle result

#### Scenario: Update a project skill through the command
- **WHEN** a caller invokes `agent-router skill update` with exactly one agent, project scope, an explicit project root, and valid update input
- **THEN** the command performs the selected local replacement and emits its deterministic lifecycle outcome

#### Scenario: Select exact ignore policy by default
- **WHEN** a caller omits the Git-ignore policy from an otherwise valid project skill update
- **THEN** the library or command uses exact per-skill ignore policy

#### Scenario: Supply pattern ignore policy
- **WHEN** a caller selects pattern policy and supplies one explicit Git ignore pattern
- **THEN** the library or command passes that validated policy to project update

#### Scenario: Reject incomplete pattern policy
- **WHEN** pattern policy has no pattern, a pattern accompanies another policy, or multiple pattern values are supplied
- **THEN** the operation reports invalid input before project or destination mutation

#### Scenario: Disable ignore mutation explicitly
- **WHEN** a caller selects none policy
- **THEN** the operation performs project update without consulting or changing Git-ignore state

#### Scenario: Reject user-scope update command
- **WHEN** `skill update` selects or defaults to user scope
- **THEN** the command reports invalid scope before target inspection or mutation

#### Scenario: Update an explicit project destination
- **WHEN** project skill update supplies both its required project root and a destination override
- **THEN** the operation replaces that exact target while retaining project-scoped router state and Git-ignore semantics
