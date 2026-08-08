Feature: Manage Agent Skills
  Agent-router safely inspects and manages one source-native skill for one agent.

  Scenario Outline: Inspect a portable skill
    Given a valid portable Agent Skill
    When I inspect the skill for <agent>
    Then the skill is reported as natively compatible
    And no destination is changed

    Examples:
      | agent  |
      | kimi   |
      | pi     |
      | claude |
      | codex  |

  Scenario: Install a Codex skill in the default scope
    Given a valid portable Agent Skill named "reviewer"
    When I install the skill for Codex without selecting a scope
    Then the owned skill is installed beneath "~/.codex/skills"
    And the lifecycle result reports user scope

  Scenario Outline: Install a repository-local skill
    Given a valid portable Agent Skill named "reviewer"
    And an explicit project root
    When I install the skill for <agent> in project scope
    Then the owned skill is installed through the agent's native project skill surface

    Examples:
      | agent  |
      | kimi   |
      | pi     |
      | claude |
      | codex  |

  Scenario: Reject an incompatible skill instead of converting it
    Given a valid skill that is not compatible with Codex
    When I install the skill for Codex with conversion allowed
    Then the operation reports an unsupported asset
    And neither the source nor destination is changed

  Scenario: Reject symbolic links in a skill
    Given a skill containing a symbolic link
    When I inspect the skill for Codex
    Then the operation reports invalid source content
    And the symbolic link is not followed

  Scenario: Repeat an identical skill installation
    Given an intact skill projection installed by agent-router
    When I install the identical skill to the same destination
    Then installation succeeds as a no-op
    And unrelated destination content is unchanged

  Scenario: Reconcile an outdated owned skill
    Given an intact older skill projection installed by agent-router
    When I install the newer skill to the same destination
    Then only the owned skill projection is replaced
    And unrelated destination content is unchanged

  Scenario: Refuse an unmanaged skill conflict
    Given a same-named skill not installed by agent-router
    When I install a managed skill to that destination
    Then the operation reports a conflict
    And the existing skill is unchanged

  Scenario: Uninstall an intact owned skill by name
    Given an intact skill projection installed by agent-router
    When I uninstall the skill by name without its original source
    Then only that owned skill projection is removed
    And neighboring skills are retained

  Scenario Outline: Refuse unsafe skill removal
    Given a same-named skill that is <state>
    When I uninstall the skill by name
    Then the operation reports an ownership conflict
    And the skill is not removed

    Examples:
      | state                              |
      | not installed by agent-router      |
      | modified after managed installation |

  Scenario: Reject a multi-agent skill operation
    Given a valid portable Agent Skill
    When I request one skill operation for Codex and Claude
    Then the request is rejected before destination mutation
