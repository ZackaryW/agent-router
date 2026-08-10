# Agent Hook Lifecycle Specification

## Purpose

Provides ownership-aware installation and uninstallation of native lifecycle hooks or hook-equivalent integrations for four supported coding agents.

## Requirements

### Requirement: Supported agent hook integration
The system SHALL inspect, install/reconcile, and uninstall hook integrations for one explicitly selected Kimi, Pi, Claude Code, or Codex target per operation through that agent's supported native configuration or extension surface.

#### Scenario: Install hooks for a supported agent
- **WHEN** a caller supplies an accepted hook integration and explicitly selects one supported agent
- **THEN** the system installs the corresponding native hook or hook-equivalent integration for that agent

#### Scenario: Reject a multi-agent hook operation
- **WHEN** a caller attempts to select more than one agent for one hook lifecycle operation
- **THEN** the system rejects the request before destination mutation

### Requirement: Source-native hook loading
The system SHALL load one existing local hook artifact per inspection or installation request, validate its structure and content without destination mutation, and identify the agents with which its native format is compatible. Malformed, ambiguous, or symlinked artifact roots or entries SHALL be rejected rather than followed or assigned compatibility by filename alone.

#### Scenario: Detect native hook compatibility
- **WHEN** a caller loads a valid native hook artifact
- **THEN** the system reports the agents that can consume that artifact natively without changing any agent destination

#### Scenario: Reject an ambiguous hook artifact
- **WHEN** a hook artifact cannot be validated as a supported native format
- **THEN** the system reports an invalid or ambiguous asset without guessing an agent or changing any destination

#### Scenario: Reject a symlinked hook artifact
- **WHEN** a hook artifact root or contained entry is a symbolic link
- **THEN** the system reports invalid source content without following the link or changing any destination

### Requirement: Copy before limited conversion
The system SHALL project a natively compatible hook artifact without semantic translation. The first release SHALL support conversion only between Claude Code and Codex dedicated hook configuration files, in either direction, and only for their portable command-hook subset: events supported by both agents, command handlers, and the shared matcher, command, and timeout fields. The converter SHALL reject rather than discard every unsupported event, handler type, or field. Conversion SHALL be disabled by default and SHALL run only when the caller explicitly authorizes it for that installation operation. The system SHALL validate converted configuration for the target agent before mutation. Conversion guarantees supported configuration structure and represented event/matcher/command mapping; opaque hook-script runtime behavior remains caller-owned and SHALL NOT be represented as semantically verified.

#### Scenario: Install a natively compatible hook artifact
- **WHEN** the loaded hook artifact is natively compatible with the selected agent
- **THEN** the system copies the dedicated artifact or reconciles only its owned entries into the agent's native surface without translating its represented behavior

#### Scenario: Reject an unavailable hook conversion
- **WHEN** the loaded hook artifact is not a portable Claude Code or Codex command-hook configuration for the opposite supported target
- **THEN** the system reports the unsupported conversion without generating a best-effort artifact or changing the destination

#### Scenario: Require hook conversion authorization
- **WHEN** the loaded hook artifact is not natively compatible with the selected agent, an explicit converter exists, and the caller has not authorized conversion
- **THEN** the system reports an unsupported-asset outcome without running the converter or changing the destination

#### Scenario: Apply an authorized hook conversion
- **WHEN** the caller authorizes conversion for a portable Claude Code or Codex command-hook configuration targeting the other agent
- **THEN** the system validates and installs the converted native configuration without modifying the source artifact or claiming to verify the opaque hook script's runtime behavior

#### Scenario: Reject a lossy command-hook conversion
- **WHEN** an otherwise convertible Claude Code or Codex hook contains an event, handler type, or field outside the portable subset
- **THEN** the system rejects conversion without dropping content or changing the destination

### Requirement: Explicit user and project hook scopes
The system SHALL support user-global and repository-local hook scopes for Claude Code and Codex, user-global Kimi hooks, and user-global and repository-local Pi hook-equivalent extensions. User-global SHALL be the default scope. Repository-local resolution SHALL use an explicitly supplied project root rather than the process working directory. Kimi project hooks and every other unsupported agent, asset, and scope combination SHALL be rejected with a typed unsupported-scope outcome before mutation.

#### Scenario: Use the default hook scope
- **WHEN** a caller omits the scope from an otherwise valid hook lifecycle request
- **THEN** the system uses user-global scope

#### Scenario: Install a repository-local hook integration
- **WHEN** a caller selects project scope, supplies a project root, and the selected agent supports a native project hook surface
- **THEN** the system installs the managed integration through that native surface for the supplied repository

#### Scenario: Reject an unsupported project hook scope
- **WHEN** a caller selects project scope for Kimi hooks
- **THEN** the system reports an unsupported-scope outcome without inventing a configuration convention or changing the repository

### Requirement: Exact predecessor hook reconciliation
Hook inspection and installation SHALL accept zero or more caller-supplied exact predecessor hook assets for the selected current hook. Each predecessor SHALL be loaded and validated through the ordinary hook source contract, SHALL be natively compatible with the selected agent and scope without conversion, and SHALL participate only because the caller explicitly supplied it. The system SHALL NOT discover or infer a predecessor from a destination, command prefix, filename, version, event alone, or caller-specific convention.

When exactly one complete predecessor exists without structural ambiguity, inspection SHALL report a recoverable outdated integration and installation SHALL remove only that predecessor, reconcile the exact current hook, and publish current ownership in one destination mutation. When an intact current owned hook and exactly one predecessor coexist, installation SHALL retain the current hook and remove only the predecessor. Multiple present predecessors, partial matches, duplicates, misplaced recognized handlers, or incompatible predecessor assets SHALL be rejected without mutation.

#### Scenario: Replace one exact predecessor
- **WHEN** a caller supplies one exact natively compatible predecessor that is wholly present and the current hook is absent
- **THEN** installation removes that predecessor, installs the current hook, records current ownership, and reports a legacy-replaced transition

#### Scenario: Prune a predecessor beside the current hook
- **WHEN** the intact current owned hook and one exact supplied predecessor coexist
- **THEN** installation removes only the predecessor, retains the current hook and ownership, preserves unrelated configuration, and reports a legacy-pruned transition

#### Scenario: Reject inferred predecessor ownership
- **WHEN** native content merely resembles a predecessor by command prefix, filename, event, or partial structure
- **THEN** inspection reports a conflict or unmanaged state without claiming or changing that content

#### Scenario: Reject ambiguous predecessor evidence
- **WHEN** multiple supplied predecessors are present, one is only partially present, or a recognized handler is misplaced
- **THEN** the operation fails before native destination mutation

### Requirement: Preserve native agent configuration
Hook installation SHALL validate the selected native destination before mutation, preserve unrelated configuration and hook entries, reject malformed or conflicting state without overwrite, make an identical repeated installation a successful no-op, and reconcile an outdated intact integration already owned by `agent-router` without a separate update operation.

When a valid ownership record identifies the selected hook and destination but the exact recorded projection is wholly absent with no partial or competing recognized structure, inspection SHALL report a recoverable outdated state and explicit installation SHALL restore the current hook. A partially present, structurally overlapping, duplicated, or otherwise ambiguous recorded projection SHALL remain a conflict.

#### Scenario: Reconcile with unrelated hooks
- **WHEN** a valid native configuration contains unrelated hook entries and no conflict with the intended managed integration
- **THEN** the system adds the managed integration while retaining the unrelated entries unchanged

#### Scenario: Reject malformed hook configuration
- **WHEN** the selected native hook destination is malformed or cannot be safely reconciled
- **THEN** installation fails before changing that destination

#### Scenario: Reconcile an outdated owned hook
- **WHEN** the selected destination contains an intact older hook integration owned by `agent-router`
- **THEN** installation replaces only that owned integration and preserves unrelated native configuration

#### Scenario: Restore a wholly missing owned hook
- **WHEN** valid ownership identifies the selected destination but the complete recorded hook is absent without partial or competing recognized content
- **THEN** explicit installation restores the current hook, preserves unrelated configuration, and reports an owned-restored transition

#### Scenario: Reject a partially modified owned hook
- **WHEN** part of the recorded hook remains or recognized structure overlaps ambiguously
- **THEN** installation reports a conflict and preserves the complete native destination

### Requirement: Remove only owned hook integration
Hook uninstallation SHALL address an integration by stable asset name plus the selected agent, scope, project root, and optional destination. It SHALL remove only native entries or extension paths previously installed by `agent-router` whose ownership and current installed identity the system can prove. It SHALL preserve the configuration container and all unrelated hook integrations. The original source artifact SHALL NOT be required for uninstallation.

When the ownership record is valid for the selected identity and destination but the complete recorded hook projection is wholly absent without partial recognized structure, uninstallation SHALL remove only the stale ownership record and report an owned-removed transition. It SHALL NOT recreate the hook before removal. Partial, modified, or ambiguous state SHALL remain a conflict.

#### Scenario: Uninstall from shared native configuration
- **WHEN** a valid native configuration contains both an intact managed integration and unrelated hooks
- **THEN** the system removes only the managed integration and preserves all unrelated configuration

#### Scenario: Remove stale ownership for an absent hook
- **WHEN** valid ownership identifies a wholly absent hook without partial recognized structure
- **THEN** uninstallation removes only the stale ownership record, preserves the native destination, and reports an owned-removed transition

#### Scenario: Reject ambiguous hook ownership
- **WHEN** the intended hook integration differs from its recorded installed identity or ownership is otherwise ambiguous
- **THEN** uninstallation fails without removing the ambiguous or unrelated configuration

#### Scenario: Preserve a same-named unmanaged hook
- **WHEN** a caller requests uninstallation by name but the resolved integration was not installed by `agent-router`
- **THEN** uninstallation fails without removing the integration or unrelated configuration
