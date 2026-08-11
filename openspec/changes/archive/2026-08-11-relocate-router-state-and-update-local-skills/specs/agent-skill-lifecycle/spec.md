## ADDED Requirements

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
