## Why

`agent-router` can manage individual skills and hooks, but it cannot resolve the larger plugin bundles through which Codex, Claude Code, Kimi Code, and Pi distribute combinations of skills, hooks, MCP servers, extensions, commands, and other executable capabilities. Callers need one programmable surface for finding and managing those native bundles without erasing the distinctions between the four agents' plugin systems.

## What Changes

- Add normalized discovery of installed and available native plugins or Pi packages for one explicitly selected agent, including host-reported activation evidence and canonical absolute roots for installed bundles.
- Add plugin installation, explicit update, and removal through the importable library and optional CLI.
- Preserve each agent's native plugin identity, source, version, scope, and lifecycle constraints in structured results.
- Add explicit, namespaced generic-artifact registration so dependent products can resolve artifacts within eligible plugin roots without owning agent-specific discovery adapters.
- Treat authoritative native installed state, not cache or directory presence, as the source of installation and activation truth; refresh identity, version, root, and activation before artifact resolution.
- Delegate mutations only to supported noninteractive native lifecycle surfaces, preflight the requested operation, and verify the resulting authoritative state before reporting convergence.
- Default discovery to installed state and require an explicit available-catalog request; consult only sources already configured in the selected native agent.
- Preserve exact native scopes and opaque native plugin references rather than introducing common-denominator identities or scope precedence.
- Record router-created installations so update and removal affect only router-owned plugins, require explicit trust for direct executable sources, and update exactly one selected plugin.
- Add router-owned `inherit`, `enabled`, and `disabled` policy for registered generic artifacts without overriding native plugin disablement or parsing artifact content.
- Let `--destination` and the equivalent library environment contract select the complete isolated adapter state root for deterministic testing.
- Reject cross-agent plugin conversion; this change resolves native plugin/package systems rather than inventing a portable plugin format.
- Keep discovery read-only and make every mutating operation explicit and noninteractive.

## Capabilities

### New Capabilities

- `agent-plugin-discovery`: Discover and normalize installed and available plugins from the selected agent's supported native catalogs or package sources, report activation evidence and absolute installed roots, and resolve explicitly registered generic artifacts.
- `agent-plugin-lifecycle`: Install, update, and remove native plugins or packages while preserving agent-specific policy, scope, and safety behavior.

### Modified Capabilities

- `programmatic-command-surface`: Expose plugin discovery and lifecycle through the importable agent-bound API and optional Typer CLI with deterministic structured outcomes.

## Impact

- Extends the public Python contracts, command tree, structured results, and typed errors.
- Allows products such as ZPP to become thin artifact extensions: `agent-router` owns native plugin discovery, eligibility, and path resolution while the extension owns artifact-specific parsing and composition.
- Adds agent-specific plugin adapters and capability-owned BDD coverage without merging the discovery and mutation targets.
- May require invoking installed agent executables or implementing a supported alternative for agents without a noninteractive plugin command.
- Plugin discovery may perform network access when the selected native catalog requires it; mutation may download and execute third-party plugin content.

## Unresolved — Do Not Assume

None. Marketplace and source administration is explicitly deferred from this change.
