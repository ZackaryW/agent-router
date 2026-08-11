# Agent Skill Lifecycle Specification

## Purpose

Provides safe, repeatable installation and uninstallation of owned Agent Skills across Kimi, Pi, Claude Code, and Codex without disturbing unrelated agent content.
## Requirements
### Requirement: Supported agent skill projection
The system SHALL inspect, install/reconcile, and uninstall accepted Agent Skill content for one explicitly selected Kimi, Pi, Claude Code, or Codex target per operation using that agent's native user-global or repository-local skill discovery surface. The system SHALL keep agent-specific destination policy outside the installed skill content.

#### Scenario: Install a skill for a supported agent
- **WHEN** a caller supplies accepted skill content and explicitly selects one supported agent
- **THEN** the system projects the skill through that agent's native skill discovery surface

#### Scenario: Reject a multi-agent skill operation
- **WHEN** a caller attempts to select more than one agent for one skill lifecycle operation
- **THEN** the system rejects the request before destination mutation

### Requirement: Source-native skill loading
The system SHALL load one existing local skill directory per inspection or installation request, validate its required structure and content without destination mutation, and identify the agents with which the loaded skill is natively compatible. Installation SHALL preserve compatible source content unchanged. The first release SHALL NOT convert skill content between agent formats.

#### Scenario: Load a compatible skill directory
- **WHEN** a caller loads a valid local skill directory
- **THEN** the system reports its native agent compatibility without changing any agent destination

#### Scenario: Reject an incompatible skill
- **WHEN** the loaded skill is not natively compatible with the selected agent
- **THEN** the system reports an unsupported-asset outcome without rewriting the source or changing the destination

### Requirement: Reject symlinked skill content
The system SHALL reject a skill when its source root or any contained entry is a symbolic link, without following, copying, or mutating through that link.

#### Scenario: Inspect a skill containing a symbolic link
- **WHEN** a caller inspects a skill whose source root or contained entry is a symbolic link
- **THEN** the system reports invalid source content without changing an agent destination

### Requirement: Codex user-global skill destination
Absent an explicit destination override, the system SHALL use `~/.codex/skills` as the Codex user-global skill destination and SHALL NOT substitute the shared `~/.agents/skills` root for that scope.

#### Scenario: Install a user-global Codex skill
- **WHEN** a caller installs accepted skill content for Codex in user-global scope without a destination override
- **THEN** the system projects the managed skill beneath `~/.codex/skills`

### Requirement: Explicit user and project skill scopes
The system SHALL support user-global and repository-local skill scopes for Kimi, Pi, Claude Code, and Codex in the first release. User-global SHALL be the default scope. Repository-local resolution SHALL use an explicitly supplied project root and the selected agent's native project skill surface rather than the process working directory.

#### Scenario: Use the default skill scope
- **WHEN** a caller omits the scope from an otherwise valid skill lifecycle request
- **THEN** the system uses user-global scope

#### Scenario: Install a repository-local skill
- **WHEN** a caller selects project scope, supplies a project root, and the selected agent supports a native project skill surface
- **THEN** the system projects the managed skill beneath that agent's native skill destination for the supplied repository

### Requirement: Ownership-safe skill installation
Before changing a selected skill destination, the system SHALL inspect the complete intended projection. It SHALL preserve unrelated content, reject an unmanaged conflict at an intended owned path without overwrite, treat an already identical managed projection as a successful no-op, and reconcile an outdated intact projection already owned by `agent-router` without requiring a separate update operation.

#### Scenario: Repeat a compatible installation
- **WHEN** the selected destination already contains the identical managed skill projection
- **THEN** installation succeeds without rewriting managed or unrelated content

#### Scenario: Reject an unmanaged skill conflict
- **WHEN** an unrelated or unowned entry occupies an intended managed skill path
- **THEN** installation fails before changing that destination and leaves the conflicting content unchanged

#### Scenario: Reconcile an outdated owned skill
- **WHEN** the intended destination contains an intact older projection owned by `agent-router`
- **THEN** installation replaces that owned projection with the accepted source while preserving unrelated content

### Requirement: Ownership-safe skill uninstallation
The system SHALL address skill uninstallation by stable asset name plus the selected agent, scope, project root, and optional destination. By default, it SHALL uninstall only skill paths previously installed by `agent-router` whose ownership and current installed identity it can prove. It SHALL preserve unrelated skills and SHALL reject modified, unmanaged, or ambiguous state rather than deleting it implicitly. The original source directory SHALL NOT be required for uninstallation.

The Python library MAY receive explicit `force=True` deletion authority. Forced uninstallation SHALL remove an exact skill target only when valid Agent Router ownership matches the selected agent, skill name, scope, and destination, even when the target content no longer matches its recorded fingerprint or is wholly missing. It SHALL delete the owned target without following a symbolic link, delete its current and legacy ownership records, retain no backup or history, and preserve neighboring content. A wholly absent target with no ownership record SHALL be an already-converged no-op. A present target without matching valid ownership, or malformed, ambiguous, or mismatched ownership state, SHALL remain a conflict and SHALL NOT be deleted.

#### Scenario: Remove an intact managed skill
- **WHEN** a caller uninstalls an intact projection previously owned by the system
- **THEN** the system removes only the proven owned skill paths and retains neighboring content

#### Scenario: Preserve modified managed content
- **WHEN** a managed skill path no longer matches its recorded installed identity and force is not authorized
- **THEN** uninstallation fails without deleting that path or unrelated content

#### Scenario: Force-delete modified owned content
- **WHEN** a library caller explicitly forces uninstallation of a modified skill with matching valid Agent Router ownership
- **THEN** the system removes the exact owned target and ownership records without retaining backup or history

#### Scenario: Clean missing owned content forcibly
- **WHEN** forced uninstallation finds matching valid ownership but the exact skill target is wholly missing
- **THEN** the system removes the stale ownership records and reports successful removal

#### Scenario: Converge an already absent force deletion
- **WHEN** forced uninstallation finds neither an exact target nor ownership record
- **THEN** it reports an absent no-op without creating or deleting state

#### Scenario: Preserve a same-named unmanaged skill
- **WHEN** a caller requests default or forced uninstallation by name but a present resolved skill was not installed by `agent-router`
- **THEN** uninstallation fails without deleting the skill

#### Scenario: Reject invalid forced ownership
- **WHEN** forced uninstallation encounters malformed, ambiguous, or mismatched ownership state
- **THEN** it fails without deleting the target or ownership evidence

### Requirement: Explicit authoritative project skill update
The system SHALL expose an update operation for one existing repository-local skill projection. Update SHALL require project scope and an explicit project root, validate the complete supplied source before destination mutation, and treat that source as authority to replace the exact resolved skill target even when the existing target is modified or unmanaged. User-scope installation and reconciliation SHALL retain the existing ownership-safe conflict behavior and SHALL NOT infer this replacement authority.

The operation SHALL require the exact target to exist, reject a symbolic link or other unsafe target structure, preserve unrelated sibling skills and native content, and publish ownership for the resulting projection. When the existing complete target is byte-identical to the supplied source, update SHALL succeed as a no-op without rewriting it.

#### Scenario: Replace a modified local skill
- **WHEN** a caller explicitly updates an existing modified repository-local skill from valid source content
- **THEN** the system replaces the complete exact target at its resolved path, records current ownership, and preserves neighboring content

#### Scenario: Replace an unmanaged local skill
- **WHEN** a caller explicitly updates an existing same-named unmanaged repository-local skill from valid source content
- **THEN** the system treats project update as replacement authority for that exact target without claiming or changing any sibling

#### Scenario: Reject update outside project scope
- **WHEN** a caller requests authoritative skill update in user scope or omits the explicit project root
- **THEN** the system rejects the request before inspecting or mutating a target

#### Scenario: Reject an absent update target
- **WHEN** the resolved repository-local skill target does not exist
- **THEN** update reports that no target can be replaced and does not perform installation

#### Scenario: Keep identical local content unchanged
- **WHEN** the existing complete repository-local target is byte-identical to the validated update source
- **THEN** update succeeds as a no-op without rewriting the target

#### Scenario: Reject an unsafe local target
- **WHEN** the exact local update target is a symbolic link or another unsupported filesystem entry
- **THEN** update fails without following, replacing, or mutating through that entry

### Requirement: Atomically replace the complete local skill target
Project skill update SHALL stage the complete validated source before replacing the existing target at the same stable path. It SHALL expose neither a merged projection containing stale files nor a successfully completed partial projection. Failure while changing the target, router state, or requested Git-ignore state SHALL restore the previous target and associated state.

#### Scenario: Remove stale files during update
- **WHEN** the existing target contains files absent from the validated update source
- **THEN** successful update replaces the complete target and none of those stale files remain

#### Scenario: Roll back a failed local update
- **WHEN** a filesystem or state operation fails after update begins
- **THEN** the previous complete target, ownership evidence, and Git-ignore content are restored

### Requirement: Maintain effective repository ignore policy for local update
Project skill update SHALL manage the containing Git repository's effective ignore policy by default. The default exact policy SHALL ensure both the scoped `.z-agent-router` state and only the selected skill target are ignored. A pattern policy SHALL require an explicit Git ignore pattern and SHALL ensure that pattern effectively ignores the selected target. A none policy SHALL perform no Git-ignore read or mutation as a condition of update.

Existing effective Git coverage, including a broader glob, SHALL satisfy exact or pattern policy without adding a redundant rule. Effective negation SHALL be honored rather than treating matching text as coverage. When ignore management is enabled, the system SHALL require a containing Git worktree and SHALL fail before target replacement if the requested effective policy cannot be established. It SHALL preserve unrelated ignore rules and repository files.

#### Scenario: Add exact per-skill ignore by default
- **WHEN** a project update uses the default ignore policy and neither scoped state nor the selected target is effectively ignored
- **THEN** the system adds only the rules needed to ignore `.z-agent-router` and that exact skill target

#### Scenario: Reuse existing glob coverage
- **WHEN** an existing effective Git ignore glob already covers the selected skill target
- **THEN** update accepts that coverage without adding a redundant exact target rule

#### Scenario: Apply an explicit ignore pattern
- **WHEN** a caller selects pattern policy with a valid pattern that effectively covers the selected target
- **THEN** update establishes that pattern while preserving unrelated ignore content

#### Scenario: Reject an ineffective pattern
- **WHEN** a caller-supplied pattern does not effectively ignore the selected target or is defeated by an effective negation
- **THEN** update fails without replacing the skill target

#### Scenario: Disable ignore management
- **WHEN** a caller selects none policy
- **THEN** update neither requires Git nor reads or changes repository ignore files

#### Scenario: Require Git for managed ignore policy
- **WHEN** exact or pattern policy is selected but the project root is not contained in a usable Git worktree
- **THEN** update fails before changing the skill target, router state, or project files
