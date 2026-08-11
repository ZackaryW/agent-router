## MODIFIED Requirements

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
