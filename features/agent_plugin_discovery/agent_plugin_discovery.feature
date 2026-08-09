Feature: Discover agent plugins and resolve generic artifacts
  Agent-router reports authoritative native plugin state and safely exposes registered generic artifacts.

  Scenario: Discover installed plugins by default
    Given an agent with installed, available, cached, and orphaned plugin material
    When I discover plugins without requesting available entries
    Then only plugins in the agent's authoritative installed state are returned
    And discovery does not mutate native or router state

  Scenario: Discover available plugins explicitly
    Given an agent with configured and unconfigured plugin catalogs
    When I explicitly include available plugins in discovery
    Then available entries come only from the agent's configured catalogs
    And no public gallery is searched or administered

  Scenario: Preserve an exact native plugin reference
    Given the same native plugin is installed in two supported scopes
    When I discover the plugin installations
    Then each record has a distinct opaque PluginRef retaining agent, native reference, scope, and source qualifier
    And no cross-scope precedence is asserted

  Scenario: Return only verified absolute runtime roots
    Given installed and available plugin records with predicted cache locations
    When I discover their runtime roots
    Then each authoritative materialized installation returns its canonical absolute runtime root
    And every unmaterialized or unverified record returns no runtime root

  Scenario Outline: Preserve native activation evidence
    Given <agent> reports <evidence> for an installed plugin
    When I discover that plugin
    Then its normalized activation is <state>
    And the native evidence is retained

    Examples:
      | agent  | evidence                         | state    |
      | codex  | plugin disabled                  | disabled |
      | claude | plugin enabled                   | enabled  |
      | kimi   | plugin disabled                  | disabled |
      | pi     | only some resource kinds enabled | partial  |

  Scenario: Resolve an explicit artifact extension
    Given an explicitly supplied extension with a namespaced ArtifactManifest
    And its locator returns a relative artifact path for an eligible plugin
    When I resolve that artifact identifier
    Then the locator receives an immutable PluginArtifactContext
    And the result contains the canonical absolute artifact path and effective status
    And agent-router does not parse the artifact's domain content

  Scenario: Reject an artifact path escaping the plugin root
    Given a registered artifact locator returns a path that escapes through traversal or a symbolic link
    When I resolve that artifact identifier
    Then resolution fails without returning or loading the escaped path

  Scenario: Disable one generic artifact contribution
    Given an eligible plugin contributes two registered artifact identifiers
    When I set one artifact policy to disabled
    Then only that artifact contribution becomes inactive by router policy
    And the native plugin and other artifact contribution remain unchanged

  Scenario: Keep native plugin disablement authoritative
    Given a natively disabled plugin with a registered generic artifact
    When I set that artifact policy to enabled
    Then its effective artifact status remains inactive for the native reason
    And no artifact path is returned

  Scenario: Inherit generic artifact eligibility for Pi
    Given an installed Pi package with resource-level filtering and a registered generic artifact
    When I resolve the artifact with inherited policy
    Then the package is eligible for that generic artifact
    And its native activation evidence remains partial or unknown

  Scenario: Preserve an artifact override across plugin movement
    Given a scoped plugin has an explicit artifact policy
    When its authoritative version and runtime root change
    Then the policy remains attached to its stable scoped PluginRef
    And subsequent resolution returns only the new canonical absolute artifact path

  Scenario: Clear an artifact policy override
    Given a scoped plugin has an explicit artifact policy
    When I clear that policy override
    Then its persisted override is removed
    And its effective artifact policy returns to inherit

  Scenario: Stop contributing stale plugin artifacts
    Given a plugin previously contributed a registered artifact
    When the authoritative agent state disables or removes that plugin
    Then subsequent resolution excludes its former artifact paths
    And cached files or prior contexts do not remain effective

  Scenario: Keep plugin identities agent-native
    Given two agents expose similarly named plugins
    When I discover both agents independently
    Then each plugin remains an independent native record
    And agent-router does not assert cross-agent compatibility or conversion
