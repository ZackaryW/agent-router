Feature: Store router state outside native agent surfaces
  Agent-router keeps ownership and policy metadata scoped, isolated, and migratable without exposing it as native agent content.

  Scenario Outline: Keep scoped router state outside native destinations
    Given a valid managed asset in <scope> scope
    When agent-router records ownership for the selected destination
    Then router state is stored beneath the <state-root> application-data root
    And no persistent router metadata is created in the native agent surface

    Examples:
      | scope   | state-root                   |
      | user    | selected home .z-agent-router |
      | project | selected project .z-agent-router |

  Scenario: Retain scoped state with a destination override
    Given project scope, an explicit project root, and a custom asset destination
    When agent-router records ownership for the custom projection
    Then the projection uses the custom destination
    And its metadata remains in the selected project's application-data root

  Scenario: Keep isolated plugin state outside native discovery
    Given an explicit isolated AgentEnvironment
    When plugin ownership and artifact policy are persisted
    Then router state uses only that environment's application-data root
    And no receipt or policy is exposed through a native plugin surface

  Scenario: Keep same-named projections independent
    Given two projects contain same-named managed skills for the same agent
    When each project resolves its router ownership
    Then each projection uses only the record bound to its canonical destination
    And displaced ownership evidence is rejected without mutation

  Scenario: Inspect valid legacy state without migrating it
    Given an intact managed projection has only a valid legacy relative ownership record
    When I inspect that projection
    Then inspection reports its managed state from the legacy evidence
    And neither legacy nor current router state is changed

  Scenario: Migrate valid legacy state during an authorized mutation
    Given an intact managed projection has only a valid legacy relative ownership record
    When I perform an authorized lifecycle mutation
    Then current ownership is published or consumed in the selected application-data root
    And the legacy record and only proven-empty legacy router directories are removed

  Scenario: Reject divergent current and legacy evidence
    Given current and legacy records disagree about one addressed projection
    When I inspect or mutate that projection
    Then agent-router reports an ownership conflict
    And neither state location nor the native projection is changed

  Scenario: Restore state when migration fails
    Given valid legacy ownership is ready to migrate
    When a later projection or state mutation fails
    Then the original projection and legacy ownership evidence are restored
    And successful migration is not reported
