# Agent Plugin Lifecycle Specification

## Purpose

Provides explicit installation, update, and removal of native plugin bundles while retaining each supported coding agent's own plugin or package semantics.

## Requirements

### Requirement: Supported native plugin lifecycle
The system SHALL install, update, and remove one explicitly selected native plugin or package for one Codex, Claude Code, or Pi target per operation through that agent's supported noninteractive native lifecycle surface. The system SHALL address the plugin using a native reference accepted for that agent and SHALL NOT convert plugin bundles between agent formats or directly edit native manager state as a mutation fallback. Until Kimi Code provides a supported noninteractive lifecycle surface, Kimi mutation SHALL return a typed unsupported outcome without changing its installed state.

#### Scenario: Install a native plugin
- **WHEN** a caller supplies a supported native plugin reference and explicitly selects its agent
- **THEN** the system installs the plugin through the supported lifecycle for that agent and returns its resulting native identity and state

#### Scenario: Update a native plugin
- **WHEN** a caller requests update of an installed plugin using its stable native reference
- **THEN** the system resolves and applies the supported newer native version or returns an already-current no-op

#### Scenario: Remove a native plugin
- **WHEN** a caller requests removal of an installed plugin using its stable native reference
- **THEN** the system removes that selected native installation without removing unrelated plugins

#### Scenario: Reject a cross-agent plugin reference
- **WHEN** a native plugin reference is not valid for the selected agent
- **THEN** the system rejects the operation without translating the reference or changing plugin state

#### Scenario: Defer unsupported Kimi mutation
- **WHEN** a caller requests Kimi plugin installation, update, or removal while Kimi exposes only interactive management
- **THEN** the operation reports unsupported without editing `installed.json`, managed plugin directories, or other Kimi state

### Requirement: Preserve native lifecycle constraints
Plugin lifecycle operations SHALL retain the selected agent's supported source, version, dependency, catalog, exact native scope, and policy constraints. A caller SHALL explicitly select a scope when more than one native scope could address the reference; the router SHALL NOT invent common scopes or infer precedence between coexisting installations. The system SHALL reject unsupported combinations explicitly rather than emulate an unavailable native feature or silently downgrade the request.

#### Scenario: Reject an unsupported plugin scope
- **WHEN** a caller selects a plugin scope that the target agent does not support
- **THEN** the system returns a typed unsupported-scope outcome without changing plugin state

#### Scenario: Report a native policy rejection
- **WHEN** the selected agent rejects a plugin because of source, trust, administrative, dependency, or installation policy
- **THEN** the system returns a structured rejection without bypassing that policy

#### Scenario: Keep scoped installations distinct
- **WHEN** the same native plugin reference is installed in two supported scopes
- **THEN** lifecycle operations address only the exact scope in the supplied `PluginRef` and do not assert precedence between them

### Requirement: Router-owned mutation authority
After a verified installation, the router SHALL persist an ownership receipt under its selected state root using the installed plugin's stable scoped `PluginRef` and enough native source evidence to maintain that installation safely. Update and removal SHALL operate only on an installation with a valid router ownership receipt and SHALL reject an otherwise discoverable native installation as unmanaged. Receipt decoding SHALL remain independent of the current plugin version and runtime root so an intact historical receipt can authorize safe update. Removal SHALL clear the receipt only after authoritative discovery verifies that the selected installation is absent.

#### Scenario: Record a verified installation
- **WHEN** agent-router installs a plugin and verifies its authoritative installed state
- **THEN** it records ownership for that exact agent, native reference, and scope without claiming ownership of unrelated plugins

#### Scenario: Reject mutation of an unmanaged installation
- **WHEN** a caller requests update or removal of a natively installed plugin without a valid router ownership receipt
- **THEN** the operation reports unmanaged state without invoking native mutation

#### Scenario: Update an owned historical installation
- **WHEN** a valid ownership receipt names an earlier installed version or root and authoritative state identifies its current successor under the same stable scoped reference
- **THEN** the router may update that owned installation without treating the historical receipt as malformed

### Requirement: Explicit trust for direct executable sources
An explicit install from a marketplace or catalog already configured in the selected native agent SHALL be sufficient router-level authorization, subject to all native policy. Installation from a direct URL, Git reference, or local path capable of supplying executable plugin content SHALL additionally require explicit trust. Missing trust SHALL reject before native mutation. Router trust SHALL NOT override native administrative, source, or execution policy.

#### Scenario: Install from a configured catalog
- **WHEN** a caller explicitly installs an entry from a catalog already configured in the selected agent
- **THEN** the router proceeds without an additional trust option while preserving native policy checks

#### Scenario: Reject an untrusted direct source
- **WHEN** a caller requests installation from a direct URL, Git reference, or local path without explicit trust
- **THEN** preflight rejects the request without invoking the native manager

### Requirement: Single-plugin update convergence
Each update operation SHALL target exactly one owned scoped `PluginRef`; bulk update is outside this change. For Codex, the adapter SHALL refresh only the configured marketplace that owns the selected plugin when refresh is required, then converge and verify only that plugin installation. It SHALL NOT upgrade unrelated marketplaces or plugins as an implied side effect.

#### Scenario: Update exactly one plugin
- **WHEN** a caller updates one owned plugin while other updates are available
- **THEN** the router converges only the selected scoped installation and leaves unrelated plugins unrequested

#### Scenario: Refresh the selected Codex marketplace
- **WHEN** a Codex plugin update requires current marketplace metadata
- **THEN** the adapter refreshes its owning configured marketplace and then verifies only the selected plugin's resulting state

### Requirement: Deterministic plugin mutation outcome
Every plugin mutation SHALL return a structured outcome that identifies the operation, selected agent, native reference, resulting status, scope when known, version when known, whether state changed, and whether the expected postcondition was authoritatively verified. Expected invalid, unsupported, unavailable, conflicting, indeterminate, or partially changed outcomes SHALL NOT expose implementation tracebacks.

#### Scenario: Repeat an already-converged plugin operation
- **WHEN** an install or update request finds the selected plugin already at the requested native state
- **THEN** the operation succeeds as a structured no-op without changing unrelated state

#### Scenario: Encounter an unavailable native manager
- **WHEN** the selected lifecycle cannot be performed because its required supported native management surface is unavailable
- **THEN** the system returns a deterministic unavailable-agent outcome without attempting an undocumented fallback

### Requirement: Preflight and verify native convergence
Before invoking a native mutation, the system SHALL discover and validate the selected native reference, supported scope, current authoritative state, and requested lifecycle capability. After the native manager returns, the system SHALL query authoritative installed state again and SHALL report success or an already-converged no-op only when the requested postcondition is verified. A zero process exit alone SHALL NOT establish success. The system SHALL preserve unrelated plugin state and SHALL report an indeterminate or partially changed outcome when the manager may have changed state but the postcondition cannot be verified.

#### Scenario: Reject before invoking the manager
- **WHEN** preflight finds an invalid reference, unsupported scope, unavailable capability, or conflicting request
- **THEN** the operation fails without invoking native mutation or changing plugin state

#### Scenario: Verify an installed postcondition
- **WHEN** the native manager reports successful installation
- **THEN** the router reports converged success only after authoritative discovery confirms the selected plugin's resulting installed state

#### Scenario: Report unverifiable native mutation
- **WHEN** a native manager returns after possibly changing state but authoritative rediscovery cannot establish the requested postcondition
- **THEN** the outcome reports indeterminate or partially changed state and does not claim convergence

### Requirement: Keep lifecycle independent from artifact resolution
Plugin lifecycle operations SHALL NOT locate, parse, activate, compose, or cache registered generic artifacts. Postcondition verification SHALL inspect native plugin state only.

#### Scenario: Install without resolving artifacts
- **WHEN** a plugin is installed or updated and contains a registered generic-artifact convention
- **THEN** lifecycle verification confirms native state without loading the artifact or creating derived artifact state
