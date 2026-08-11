## MODIFIED Requirements

### Requirement: Agent-bound Python lifecycle
The supported Python API SHALL expose `Agent`, `AgentRouter`, `Skill`, `Hook`, `HookTransition`, `Scope`, structured compatibility and lifecycle results, and typed domain errors. Constructing `AgentRouter` with one `Agent` SHALL bind subsequent lifecycle operations to that agent without performing filesystem mutation during construction.

`Skill.from_path` and `Hook.from_path` SHALL load and validate one existing local source asset without mutating an agent destination and SHALL make detected native-agent compatibility available to library callers. Agent-bound skill and hook inspection, installation, and uninstallation SHALL be available through Pythonic methods. Each lifecycle method SHALL use user scope by default, require an explicit `project_root` for project scope, and accept an optional `destination` override with the same behavior and safety contract as the CLI `--destination` option. Installation SHALL accept `allow_conversion`, which SHALL default to false. Hook inspection and installation SHALL accept an immutable sequence of exact predecessor `Hook` assets, defaulting to empty. Skill uninstallation SHALL accept a stable asset name, SHALL NOT require the original source, and SHALL accept explicit `force`, defaulting to false, according to the ownership-safe skill uninstallation contract. Hook uninstallation SHALL retain its existing signature and behavior. Methods SHALL return structured results or raise typed domain errors rather than terminating the process.

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

#### Scenario: Force-delete through the library
- **WHEN** a caller passes `force=True` to `AgentRouter.uninstall_skill` for a modified but validly owned projection
- **THEN** the library applies the explicit no-history forced deletion contract and returns a structured lifecycle result

#### Scenario: Keep forced deletion out of the command
- **WHEN** a caller inspects or invokes the optional skill uninstall command
- **THEN** the command exposes no force option and retains default ownership-safe uninstallation

#### Scenario: Select a library project scope
- **WHEN** a caller passes `Scope.PROJECT` and an explicit `project_root` to an agent-bound lifecycle operation
- **THEN** the library resolves the selected agent's native repository-local destination from that project root

#### Scenario: Retain project semantics with a library destination
- **WHEN** a caller selects `Scope.PROJECT` and supplies `destination` without `project_root`
- **THEN** the library rejects the request before destination inspection or mutation

#### Scenario: Report a library domain conflict
- **WHEN** a library lifecycle operation encounters expected conflicting managed state
- **THEN** it raises a typed domain error without printing CLI output or terminating the Python process

## ADDED Requirements

### Requirement: Command force-deletion exclusion
The optional command surface SHALL NOT expose a force-deletion option for skill uninstallation. Its uninstall command SHALL continue to invoke the default ownership-safe library behavior.

#### Scenario: Inspect skill uninstall help
- **WHEN** a user inspects `agent-router skill uninstall --help`
- **THEN** no force option is present
