Feature: Manage native agent plugins
  Agent-router safely converges one router-owned native plugin through supported noninteractive agent lifecycles.

  Scenario Outline: Install through a supported native manager
    Given a configured native catalog entry for <agent>
    When I install that plugin in an exact supported scope
    Then the <agent> native manager is invoked for only that plugin
    And authoritative discovery verifies the installed postcondition
    And a router ownership receipt is recorded for its scoped PluginRef

    Examples:
      | agent  |
      | codex  |
      | claude |
      | pi     |

  Scenario: Defer Kimi mutation without editing state
    Given Kimi exposes only interactive plugin lifecycle management
    When I request Kimi plugin installation, update, or removal
    Then the operation reports an unsupported lifecycle
    And no Kimi registry or managed plugin content is changed

  Scenario: Keep native scopes exact
    Given one plugin reference is installed in two native scopes
    When I update its router-owned project-scoped installation
    Then only the project-scoped PluginRef is passed to the native manager
    And the other scoped installation remains unchanged

  Scenario: Reject an unsupported native scope
    Given a plugin lifecycle request names a scope unsupported by the selected agent
    When I preflight the request
    Then the operation reports an unsupported scope
    And the native manager is not invoked

  Scenario: Install from a configured catalog without extra trust
    Given a plugin entry from a catalog already configured in the selected agent
    When I explicitly install that entry without a trust option
    Then router preflight accepts the configured source
    And native trust and administrative policy remain authoritative

  Scenario Outline: Require trust for a direct executable source
    Given an install request from a direct <source>
    When I install without explicit trust
    Then preflight rejects the request without invoking native mutation

    Examples:
      | source     |
      | URL        |
      | Git ref    |
      | local path |

  Scenario: Refuse mutation of an unmanaged native installation
    Given an installed plugin has no valid agent-router ownership receipt
    When I request update or removal
    Then the operation reports unmanaged state
    And the native manager is not invoked

  Scenario: Update an owned historical installation
    Given an intact router ownership receipt records an earlier version and root
    And authoritative state identifies its successor under the same scoped PluginRef
    When I update that plugin
    Then the historical receipt remains valid ownership evidence
    And only the selected plugin is converged and verified

  Scenario: Refresh only the selected Codex marketplace
    Given an owned Codex plugin requires current marketplace metadata
    And other marketplaces and plugins also have updates
    When I update the selected plugin
    Then only its configured owning marketplace is refreshed
    And only the selected plugin is converged

  Scenario: Remove only a router-owned plugin
    Given an installed plugin has a valid router ownership receipt
    When I remove that scoped plugin
    Then authoritative discovery verifies that exact installation is absent
    And only then is its ownership receipt cleared
    And unrelated plugins remain unchanged

  Scenario: Repeat an already-converged installation
    Given a requested plugin already has the requested authoritative installed state
    When I install it again
    Then the operation succeeds as an already-converged no-op
    And unrelated plugin state is unchanged

  Scenario: Do not trust a successful process exit alone
    Given the native manager exits successfully without establishing the requested state
    When agent-router verifies the mutation
    Then the operation does not report convergence
    And its outcome identifies the unverified resulting state

  Scenario: Report possible partial native mutation
    Given the native manager may have changed state before authoritative rediscovery fails
    When agent-router verifies the mutation
    Then the outcome reports indeterminate or partially changed state
    And agent-router does not claim rollback it cannot prove

  Scenario: Keep plugin lifecycle independent from artifacts
    Given a plugin contains a registered generic artifact
    When I install or update that plugin
    Then lifecycle verification inspects only authoritative native plugin state
    And no generic artifact is located, parsed, activated, or cached

  Scenario: Report an unavailable native manager
    Given the selected agent's supported native manager is unavailable
    When I request a plugin lifecycle operation
    Then the outcome reports the unavailable agent deterministically
    And no undocumented fallback mutates state

  Scenario: Persist plugin authority outside native discovery
    Given a plugin installation is authoritatively verified
    When agent-router records its scoped ownership and artifact policy
    Then the receipt and policy use the selected router application-data root
    And no router metadata is added to native plugin discovery or runtime content
