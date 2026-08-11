## MODIFIED Requirements

### Requirement: Router-owned mutation authority
After a verified installation, the router SHALL persist an ownership receipt beneath the router-state root selected by the plugin environment using the installed plugin's stable scoped `PluginRef` and enough native source evidence to maintain that installation safely. The receipt SHALL remain outside native plugin registry, cache, runtime, and artifact discovery surfaces. Update and removal SHALL operate only on an installation with a valid router ownership receipt and SHALL reject an otherwise discoverable native installation as unmanaged. Receipt decoding SHALL remain independent of the current plugin version and runtime root so an intact historical receipt can authorize safe update or migration. Removal SHALL clear the receipt only after authoritative discovery verifies that the selected installation is absent.

#### Scenario: Record a verified installation
- **WHEN** agent-router installs a plugin and verifies its authoritative installed state
- **THEN** it records ownership beneath the selected scoped router-state root for that exact agent, native reference, and scope without claiming ownership of unrelated plugins

#### Scenario: Reject mutation of an unmanaged installation
- **WHEN** a caller requests update or removal of a natively installed plugin without a valid router ownership receipt
- **THEN** the operation reports unmanaged state without invoking native mutation

#### Scenario: Update an owned historical installation
- **WHEN** a valid ownership receipt names an earlier installed version or root and authoritative state identifies its current successor under the same stable scoped reference
- **THEN** the router may update that owned installation without treating the historical receipt as malformed

#### Scenario: Keep plugin state outside native discovery
- **WHEN** the router records plugin ownership or artifact-policy state
- **THEN** it writes only beneath the selected router-state root and does not add router metadata to a native plugin surface
