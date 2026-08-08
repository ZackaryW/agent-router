Feature: Manage agent hooks
  Agent-router preserves native configuration while managing one hook integration.

  Scenario Outline: Install a hook through a supported native scope
    Given a valid native <agent> hook artifact
    And the <scope> scope inputs are complete
    When I install the hook for <agent> in <scope> scope
    Then the integration is installed through that native surface
    And unrelated native configuration is retained

    Examples:
      | agent  | scope   |
      | kimi   | user    |
      | pi     | user    |
      | pi     | project |
      | claude | user    |
      | claude | project |
      | codex  | user    |
      | codex  | project |

  Scenario: Reject project-local Kimi hooks
    Given a valid native Kimi hook artifact
    And an explicit project root
    When I install the hook for Kimi in project scope
    Then the operation reports an unsupported scope
    And no project hook convention is created

  Scenario: Inspect a native hook artifact
    Given a valid native Claude hook artifact
    When I inspect the hook for Claude
    Then Claude is reported as natively compatible
    And no destination is changed

  Scenario Outline: Reject an invalid hook source
    Given a hook artifact that is <state>
    When I inspect the hook for Codex
    Then the operation reports invalid source content
    And no destination is changed

    Examples:
      | state                    |
      | ambiguous                |
      | a symbolic link          |
      | containing a symbolic link |

  Scenario Outline: Convert a portable command hook with authorization
    Given a portable <source> command-hook configuration
    When I install it for <target> with conversion allowed
    Then the supported event matcher and command mapping is converted
    And the converted configuration passes target validation
    And the source artifact is unchanged

    Examples:
      | source | target |
      | claude | codex  |
      | codex  | claude |

  Scenario: Require explicit hook conversion authorization
    Given a portable Claude command-hook configuration
    When I install it for Codex without conversion allowed
    Then the operation reports an unsupported asset
    And no destination is changed

  Scenario Outline: Reject an unavailable or lossy hook conversion
    Given a hook conversion request containing <content>
    When I install it for the requested non-native agent with conversion allowed
    Then the operation reports an unsupported asset
    And no source content is dropped
    And no destination is changed

    Examples:
      | content                         |
      | a Kimi hook                     |
      | a Pi extension                  |
      | a nonportable event             |
      | a non-command handler           |
      | an unsupported handler field    |

  Scenario: Repeat an identical hook installation
    Given an intact hook integration installed by agent-router beside unrelated hooks
    When I install the identical integration to the same destination
    Then installation succeeds as a no-op
    And unrelated native configuration is unchanged

  Scenario: Reconcile an outdated owned hook
    Given an intact older hook integration installed by agent-router beside unrelated hooks
    When I install the newer integration to the same destination
    Then only the owned integration is replaced
    And unrelated native configuration is unchanged

  Scenario: Refuse malformed native hook configuration
    Given a malformed native hook destination
    When I install a managed hook integration
    Then the operation fails before mutation

  Scenario: Uninstall an intact owned hook by name
    Given an intact hook integration installed by agent-router beside unrelated hooks
    When I uninstall the hook by name without its original source
    Then only that owned integration is removed
    And unrelated native configuration is retained

  Scenario Outline: Refuse unsafe hook removal
    Given a same-named hook integration that is <state>
    When I uninstall the hook by name
    Then the operation reports an ownership conflict
    And the integration is not removed

    Examples:
      | state                              |
      | not installed by agent-router      |
      | modified after managed installation |

  Scenario: Reject a multi-agent hook operation
    Given a valid native Claude hook artifact
    When I request one hook operation for Codex and Claude
    Then the request is rejected before destination mutation
