## Purpose

Provides read-only discovery of native plugin and package inventory across Codex, Claude Code, Kimi Code, and Pi through one normalized agent-bound contract.

## ADDED Requirements

### Requirement: Agent-native plugin discovery
The system SHALL discover installed plugin or package records for one explicitly selected Codex, Claude Code, Kimi Code, or Pi target per operation using that agent's authoritative native discovery sources. Authoritative installed state, not a marketplace directory, download cache, orphaned root, or filesystem scan, SHALL determine whether a plugin is installed and active. Available-plugin discovery SHALL require an explicit request and SHALL query only catalogs or package sources already configured in the selected native agent; this change SHALL NOT search unconfigured public galleries or administer sources. Discovery SHALL NOT install, update, remove, enable, disable, or otherwise mutate plugin state.

#### Scenario: Discover plugins for one agent
- **WHEN** a caller requests plugin discovery for one supported agent
- **THEN** the system returns that agent's installed plugin records without changing native state or performing an available-catalog query

#### Scenario: Discover explicitly available plugins
- **WHEN** a caller explicitly includes available plugins for one supported agent
- **THEN** the system adds entries from that agent's configured native catalogs without searching an unconfigured public gallery

#### Scenario: Reject multi-agent discovery
- **WHEN** a caller attempts to select more than one agent for one discovery operation
- **THEN** the system rejects the request without querying or mutating another agent's plugin state

#### Scenario: Ignore unauthoritative cached material
- **WHEN** a plugin directory remains cached but the selected agent's installed-state contract does not report it as installed
- **THEN** discovery does not classify that directory as an installed or active plugin

### Requirement: Preserve native plugin identity and runtime root
Each discovered record SHALL carry an opaque stable `PluginRef` containing the selected agent, exact native reference, native scope when present, and source or catalog qualifier when required to address the installation without guessing. It SHALL also expose display name when available, installed state, available and installed versions when known, exact native scope when known, host-reported activation evidence, normalized activation state, and canonical absolute runtime root when materialized. A runtime root SHALL be host-reported or derived from authoritative installed-state fields through the agent's verified native layout, then resolved and verified as materialized. The system SHALL preserve unavailable metadata as unknown rather than inventing cross-agent values, common-denominator scopes, scope precedence, or paths.

#### Scenario: Normalize a marketplace plugin
- **WHEN** a native catalog reports a marketplace-qualified plugin and version metadata
- **THEN** the discovered record's `PluginRef` retains its native qualified reference, catalog, exact scope, version, and installation state

#### Scenario: Preserve missing metadata
- **WHEN** an agent's discovery surface omits a version, catalog, or scope
- **THEN** the corresponding normalized field is unknown and the record remains usable by its native reference

#### Scenario: Resolve an installed runtime root
- **WHEN** the selected agent reports an installed plugin loaded from a materialized directory
- **THEN** the record contains the canonical absolute path of that effective runtime directory

#### Scenario: Keep an unmaterialized catalog path unknown
- **WHEN** an available plugin has no materialized runtime directory
- **THEN** the record contains no runtime root instead of a predicted cache or destination path

#### Scenario: Reject an unverified reconstructed root
- **WHEN** an adapter can predict a cache path but cannot establish it from the plugin's authoritative installed-state record
- **THEN** the record contains no runtime root and the predicted directory is not eligible for artifact resolution

### Requirement: Non-lossy activation discovery
Discovery SHALL expose whether native plugin activation is enabled, disabled, partial, or unknown and SHALL retain the native evidence from which that state was derived. The system SHALL NOT collapse resource-level filtering into a false package-level Boolean.

#### Scenario: Query a plugin-level disabled state
- **WHEN** Codex, Claude Code, or Kimi reports that an installed plugin is disabled
- **THEN** the record reports `disabled` and preserves the host evidence

#### Scenario: Query Pi resource filtering
- **WHEN** Pi reports include or exclude filters for resource kinds within an installed package
- **THEN** the record preserves those filters and reports `partial` or `unknown` as appropriate without claiming that Pi supplied a package-level disabled Boolean

### Requirement: Explicit generic-artifact resolution
The library SHALL accept explicit generic-artifact extensions implementing a stable interface contract. Each extension SHALL expose an `ArtifactManifest` with a namespaced identifier and contract version and a locator that receives an immutable `PluginArtifactContext` and returns zero or more paths relative to the plugin root. The router SHALL resolve those candidates to canonical absolute artifact paths, reject every path escaping the plugin root after symbolic-link resolution, and return the absolute paths with their plugin context and effective artifact status. The router SHALL NOT discover or execute arbitrary extension code, and SHALL NOT parse domain-specific artifact semantics.

#### Scenario: Resolve a registered artifact convention
- **WHEN** a caller resolves an explicitly registered artifact type for an eligible installed plugin
- **THEN** the extension locator receives the immutable plugin context, returns relative candidates, and the router returns canonical absolute matching paths within the runtime root

#### Scenario: Reject an escaping artifact path
- **WHEN** an artifact locator resolves through traversal or a symbolic link outside the plugin runtime root
- **THEN** resolution fails without returning or loading the escaped path

#### Scenario: Keep domain semantics in the extension
- **WHEN** a registered artifact path contains product-specific documents such as ZPP traits
- **THEN** the router returns safe paths and plugin context without parsing conditions, replacement, overlays, or composition

### Requirement: Router-owned artifact activation policy
For each registered artifact identifier and installed plugin reference, the router SHALL expose a policy of `inherit`, `enabled`, or `disabled` and an effective status with a reason. Native disabled or uninstalled state SHALL always make the artifact inactive regardless of router policy. Router `disabled` SHALL suppress only that artifact contribution and SHALL NOT disable the native plugin or another artifact identifier. Router `enabled` SHALL permit contribution only when the native plugin is eligible. `inherit` SHALL use native eligibility; an installed Pi package SHALL be eligible for generic artifacts because Pi exposes resource filters rather than a package-level disabled Boolean, while those filters remain available as native evidence.

The router SHALL persist only explicit policy overrides under its selected state root, keyed by agent, exact native scope, opaque native plugin reference, and artifact identifier without plugin version or runtime root. The policy SHALL therefore survive plugin updates and moves while freshness resolution follows the new authoritative root. Clearing an override SHALL restore `inherit`.

#### Scenario: Disable one artifact contribution
- **WHEN** a caller sets `zpp.traits` to `disabled` for one eligible plugin
- **THEN** subsequent `zpp.traits` resolution omits that plugin while its native plugin and other registered artifacts remain unchanged

#### Scenario: Keep native disablement authoritative
- **WHEN** a caller sets an artifact to `enabled` for a natively disabled or uninstalled plugin
- **THEN** the effective status remains inactive with the native reason and no artifact path is returned

#### Scenario: Inherit eligibility for an installed Pi package
- **WHEN** an installed Pi package has resource-level filtering and no explicit router artifact override
- **THEN** its generic artifact uses inherited eligible status while the native activation evidence remains partial or unknown

#### Scenario: Preserve a toggle across plugin movement
- **WHEN** a plugin with an explicit artifact policy is updated to a new version and runtime root
- **THEN** the policy remains attached to its stable scoped native reference and resolution uses only the new canonical absolute path

#### Scenario: Clear an artifact override
- **WHEN** a caller clears an explicit artifact policy
- **THEN** the persisted override is removed and effective status returns to `inherit`

### Requirement: Fresh artifact eligibility
Before every generic-artifact resolution, the router SHALL re-evaluate the selected agent's authoritative installed state and the plugin's identity, version, activation evidence, and canonical runtime root. A definitively disabled, moved, updated, or uninstalled plugin SHALL cease contributing its previous artifact paths. Resolution SHALL NOT reuse a stale plugin context merely because its former root or a derived cache remains present.

#### Scenario: Follow an updated plugin root
- **WHEN** an installed plugin's active version or canonical runtime root changes
- **THEN** the next artifact resolution returns paths only from the newly authoritative root

#### Scenario: Exclude a disabled or removed plugin
- **WHEN** a previously eligible plugin becomes disabled or is no longer installed
- **THEN** its former artifact paths are absent from subsequent resolution even when the files remain cached

### Requirement: No cross-agent plugin conversion
Discovery SHALL represent each plugin as an agent-native bundle and SHALL NOT claim that a plugin discovered for one agent is installable by another agent unless that other agent independently discovers a native entry for it.

#### Scenario: Find similar plugins in two agents
- **WHEN** two agents expose plugins with similar names or components
- **THEN** the system returns independent agent-native records without merging their identities or asserting format compatibility
