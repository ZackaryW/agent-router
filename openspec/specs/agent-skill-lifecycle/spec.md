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
The system SHALL address skill uninstallation by stable asset name plus the selected agent, scope, project root, and optional destination. It SHALL uninstall only skill paths previously installed by `agent-router` whose ownership and current installed identity it can prove. It SHALL preserve unrelated skills and SHALL reject modified, unmanaged, or ambiguous state rather than deleting it implicitly. The original source directory SHALL NOT be required for uninstallation.

#### Scenario: Remove an intact managed skill
- **WHEN** a caller uninstalls an intact projection previously owned by the system
- **THEN** the system removes only the proven owned skill paths and retains neighboring content

#### Scenario: Preserve modified managed content
- **WHEN** a managed skill path no longer matches its recorded installed identity
- **THEN** uninstallation fails without deleting that path or unrelated content

#### Scenario: Preserve a same-named unmanaged skill
- **WHEN** a caller requests uninstallation by name but the resolved skill was not installed by `agent-router`
- **THEN** uninstallation fails without deleting the skill

