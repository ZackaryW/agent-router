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

  Scenario: Force-delete a modified owned skill without history
    Given a managed skill modified after installation
    And a neighboring skill outside the owned target
    When I force-uninstall the skill through the Python library
    Then the exact owned skill and ownership records are removed
    And no backup or history of the removed skill is retained
    And the neighboring skill is retained

  Scenario: Force-clean stale ownership for missing content
    Given a managed skill target removed outside agent-router
    When I force-uninstall the skill through the Python library
    Then its stale ownership records are removed
    And the lifecycle result reports removal

  Scenario: Treat wholly absent forced removal as converged
    Given no skill target or ownership record exists
    When I force-uninstall the skill through the Python library
    Then the lifecycle result reports an absent no-op
    And no destination or ownership state is created

  Scenario: Refuse forced deletion of an unmanaged skill
    Given a same-named skill not installed by agent-router
    When I force-uninstall the skill through the Python library
    Then the operation reports an ownership conflict
    And the skill is not removed

  Scenario: Keep force deletion out of the command surface
    Given the optional agent-router command is available
    When I inspect skill uninstall help
    Then no force deletion option is exposed

  Scenario: Reject a multi-agent skill operation
    Given a valid portable Agent Skill
    When I request one skill operation for Codex and Claude
    Then the request is rejected before destination mutation

  Scenario Outline: Fully replace an existing local skill
    Given an existing repository-local skill that is <state>
    And a valid authoritative update source with different files
    When I explicitly update that skill in project scope
    Then the complete exact target is replaced from the update source
    And stale target files are removed while neighboring skills are retained
    And current project ownership is recorded

    Examples:
      | state     |
      | modified  |
      | unmanaged |

  Scenario: Repeat an identical local skill update
    Given an existing repository-local skill identical to the update source
    When I explicitly update that skill in project scope
    Then update succeeds as a no-op without rewriting the target

  Scenario Outline: Reject a local update without a safe existing target
    Given a repository-local skill target that is <state>
    When I explicitly update that skill in project scope
    Then update fails before target or router-state mutation

    Examples:
      | state                   |
      | absent                  |
      | a symbolic link         |
      | an unsupported entry    |

  Scenario: Reject authoritative update outside project scope
    Given a valid authoritative update source
    When I request skill update without explicit project scope and project root
    Then the request is rejected before target inspection or mutation
    And user-scope conflict protection remains unchanged

  Scenario: Restore a local skill when update fails
    Given an existing repository-local skill and valid authoritative update source
    When target, ownership, migration, or requested Git-ignore mutation fails during update
    Then the complete previous target and associated state are restored
    And no partial or merged projection is reported as updated

  Scenario: Ignore only the updated skill by default
    Given a Git repository whose project state and selected skill are not ignored
    When I update the local skill with default ignore policy
    Then the repository ignores its .z-agent-router state and that exact skill target
    And unrelated skills and ignore rules remain visible and unchanged

  Scenario: Reuse effective glob ignore coverage
    Given an existing Git ignore glob effectively covers the selected skill target
    When I update the local skill with exact ignore policy
    Then update accepts the effective coverage without adding a redundant target rule

  Scenario Outline: Apply an explicit Git ignore pattern
    Given a caller supplies a pattern that is <effect>
    When I update the local skill with pattern ignore policy
    Then the update <outcome> before target replacement

    Examples:
      | effect                                  | outcome                              |
      | effective for the selected target       | establishes that pattern             |
      | ineffective for the selected target     | fails without changing the repository |
      | defeated by an effective negation       | fails without changing the repository |

  Scenario: Disable Git ignore management
    Given a project directory that need not be a Git worktree
    When I update the local skill with none ignore policy
    Then update does not inspect or change Git ignore state

  Scenario: Require a Git worktree for managed ignore policy
    Given a project directory outside a usable Git worktree
    When I update the local skill with exact or pattern ignore policy
    Then update fails before changing the target, router state, or project files
