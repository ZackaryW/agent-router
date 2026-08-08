Feature: Use agent-router as a library or optional command
  The same deterministic lifecycle is available to Python and unattended uvx callers.

  Scenario: Import the base library without CLI dependencies
    Given the base distribution is installed without the cli extra
    When I import agent_router and its public contracts
    Then the import succeeds without Typer

  Scenario: Explain a missing CLI extra
    Given the base distribution is installed without the cli extra
    When I invoke the optional command surface
    Then the error tells me to install "agent_router[cli]"
    And no optional dependency traceback is shown

  Scenario: Install only from GitHub
    Given the supported distribution files
    When I inspect the installation contract
    Then base and CLI installations source agent-router from GitHub
    And no package-index installation is offered
    And Git builds retain library and CLI metadata
    And project metadata supports Python 3.11 and later

  Scenario: Install a skill through the agent-bound library
    Given a valid portable Agent Skill
    When I call AgentRouter for Codex to install the loaded Skill
    Then the operation returns a structured Codex lifecycle result

  Scenario Outline: Expose each command lifecycle
    Given the cli extra is installed
    When I invoke "agent-router <kind> <operation>" with one explicit agent
    Then the request is handled through the public library lifecycle
    And no interactive selection or confirmation is required

    Examples:
      | kind  | operation |
      | skill | inspect   |
      | skill | install   |
      | skill | uninstall |
      | hook  | inspect   |
      | hook  | install   |
      | hook  | uninstall |

  Scenario: Manage an agent before its executable is installed
    Given the selected agent executable is absent
    When I invoke a valid filesystem lifecycle command
    Then the lifecycle proceeds without probing for the executable

  Scenario Outline: Override the physical destination
    Given a valid lifecycle request in <scope> scope
    And an explicit destination
    When I <operation> the asset
    Then the exact destination is handled through the production ownership planner
    And the lifecycle result retains <scope> scope

    Examples:
      | operation | scope   |
      | inspect   | user    |
      | install   | user    |
      | uninstall | user    |
      | inspect   | project |
      | install   | project |
      | uninstall | project |

  Scenario: Require a project root with a destination override
    Given project scope and an explicit destination
    But no project root
    When I request a lifecycle operation
    Then the request is rejected before destination inspection or mutation

  Scenario: Emit JSON for automation
    Given a valid lifecycle command with "--json"
    When the command completes
    Then one stable result envelope is written to standard output
    And diagnostics are written only to standard error

  Scenario Outline: Return deterministic process status
    Given a command resulting in <outcome>
    When the command exits
    Then its process status is <status>
    And expected domain errors do not show implementation tracebacks

    Examples:
      | outcome                  | status |
      | success                  | 0      |
      | already-converged no-op  | 0      |
      | invalid request          | 2      |
      | unsupported request      | 2      |
      | ownership conflict       | 3      |
      | destination conflict     | 3      |
      | unexpected failure       | 1      |
