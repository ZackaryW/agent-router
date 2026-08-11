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

  Scenario: Use plugin and artifact contracts without CLI dependencies
    Given the base distribution is installed without the cli extra
    When I construct an agent-bound router with an AgentEnvironment and an artifact extension
    Then PluginRef, ArtifactManifest, policy, status, discovery, resolution, and lifecycle contracts are available
    And Typer is not imported

  Scenario Outline: Expose plugin commands through the public lifecycle
    Given the cli extra is installed
    When I invoke "agent-router plugin <operation>" with one explicit agent
    Then the request is handled through the public agent-bound library
    And no interactive agent selection is required

    Examples:
      | operation       |
      | discover        |
      | install         |
      | update          |
      | remove          |
      | artifact status |
      | artifact set    |

  Scenario: Keep available plugin discovery explicit
    Given the cli extra is installed
    When I invoke plugin discovery with and without "--available"
    Then the default result contains installed plugins only
    And the explicit result may include configured native catalog entries

  Scenario: Query and set generic artifact policy
    Given a scoped PluginRef and a registered artifact identifier
    When I query status and set inherit, enabled, or disabled through the library or CLI
    Then the result reports requested policy, effective status, reason, and canonical absolute paths
    And native plugin enablement is unchanged

  Scenario: Isolate complete plugin adapter state
    Given an explicit plugin destination and equivalent AgentEnvironment
    When I discover, mutate, or resolve artifacts for the selected agent
    Then native adapter paths, ownership receipts, and artifact policies use only the isolated root
    And default agent and router state are neither read nor written
    And the destination is not treated as an arbitrary plugin runtime directory

  Scenario Outline: Expose each command lifecycle
    Given the cli extra is installed
    When I invoke "agent-router <kind> <operation>" with one explicit agent
    Then the request is handled through the public library lifecycle
    And no interactive selection or confirmation is required

    Examples:
      | kind  | operation |
      | skill | inspect   |
      | skill | install   |
      | skill | update    |
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
      | update    | project |
      | uninstall | project |

  Scenario: Require a project root with a destination override
    Given project scope and an explicit destination
    But no project root
    When I request a lifecycle operation
    Then the request is rejected before destination inspection or mutation

  Scenario: Update a local skill through the library and command
    Given a valid authoritative skill update and existing project target
    When I invoke update_skill or "agent-router skill update" with explicit project scope
    Then the request uses the complete-target project update lifecycle
    And the result is structured for the library or deterministic for the command

  Scenario Outline: Validate public Git ignore policy
    Given a project skill update selects <policy>
    When the library or command validates its ignore options
    Then the request is <outcome> before project mutation

    Examples:
      | policy                              | outcome  |
      | exact without a pattern             | accepted |
      | pattern with one explicit pattern   | accepted |
      | none without a pattern              | accepted |
      | pattern without a pattern           | rejected |
      | exact with a pattern                | rejected |
      | none with a pattern                 | rejected |

  Scenario: Reject user-scope skill update
    Given a valid authoritative skill update source
    When update_skill or "agent-router skill update" selects user scope
    Then the request is rejected before target inspection or mutation

  Scenario: Emit JSON for automation
    Given a valid lifecycle command with "--json"
    When the command completes
    Then one stable result envelope is written to standard output
    And diagnostics are written only to standard error

  Scenario: Supply exact predecessors through the hook lifecycle
    Given a current hook and zero or more exact native predecessor hooks
    When I inspect or install through the agent-bound library or repeatable hook predecessor command options
    Then every predecessor is validated for the selected agent and semantic scope
    And hook inspect and install receive the same immutable predecessor sequence
    And skill lifecycle and hook uninstall expose no predecessor input

  Scenario: Report hook transitions independently of source conversion
    Given a hook operation reconciles an exact predecessor or wholly missing owned projection
    When its structured lifecycle result is returned or serialized
    Then the result contains the applicable hook transition
    And converted continues to describe only authorized cross-agent source conversion

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
