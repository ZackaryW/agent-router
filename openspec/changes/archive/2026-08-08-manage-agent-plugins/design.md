## Context

See `proposal.md` for motivation and the confirmed product boundary. The current implementation treats skills and hooks as local assets copied or reconciled through agent-specific destinations. Native plugins are a different class: they can aggregate executable extensions, hooks, skills, MCP servers, language servers, dependencies, credentials, and persistent data, and their hosts maintain catalogs, registries, caches, and policy.

Research against the current installed CLIs and primary documentation found this native matrix:

| Agent | Discovery | Activation evidence | Install | Update | Remove | Native scopes |
|---|---|---|---|---|---|---|
| Codex | `codex plugin list --available --json` over configured marketplaces | plugin-level enabled state from list/read | `codex plugin add` | refresh marketplace snapshot, then converge the selected install | `codex plugin remove` | user configuration in the current CLI |
| Claude Code | `claude plugin list --available --json` | plugin-level enable status | `claude plugin install` | `claude plugin update` | `claude plugin uninstall` | user, project, local; managed update is host-controlled |
| Kimi Code | `/plugins`, `/plugins list`, and marketplace views inside the TUI | plugin-level enabled state in installed plugin state | `/plugins install` | reinstall or select an available update in the TUI | `/plugins remove` | user only |
| Pi | `pi list` for installed packages; public discovery is the Pi package gallery/npm metadata | per-resource-kind include/exclude filters, not one package Boolean | `pi install` | `pi update <source>` | `pi remove` | user and project (`-l`) |

Primary references:

- Codex's current CLI help and [official app-server plugin/marketplace surface](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md)
- [Claude Code plugin reference](https://code.claude.com/docs/en/plugins-reference) and [marketplace discovery guide](https://code.claude.com/docs/en/discover-plugins)
- [Kimi Code plugins](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/plugins.html) and [data locations](https://www.kimi.com/code/docs/en/kimi-code-cli/configuration/data-locations.html)
- [Pi packages](https://pi.dev/docs/latest/packages) and [Pi package catalog](https://pi.dev/packages)

ZPP's temporal setup history and current canonical specifications add constraints that native documentation alone does not expose. Earlier setup attempts guessed shared agent roots, installed hooks without the complete required workflow surface, and could report success while required Codex skills were absent. Later corrections moved Pi to native `.pi` roots, moved global Codex skills to `~/.codex/skills` after runtime verification, required complete preflight before selected-agent mutation, and restricted plugin traits to authoritative active-plugin state. These are historical lessons rather than authority by themselves; the current ZPP specifications confirm the authoritative-state, preflight, freshness, and installation-side-effect boundaries relevant to this change.

## Goals / Non-Goals

**Goals:**

- Keep one public agent-bound lifecycle while retaining enough native metadata to perform a later operation without guessing.
- Keep discovery and mutation adapters independently testable and independently selectable by the repository's affected-verification mapping.
- Return a canonical absolute runtime root for every materialized installed bundle and expose registered generic artifact paths as canonical absolute paths within that root.
- Let dependent products register thin, domain-specific artifact extensions without reimplementing native plugin discovery.
- Let callers query and override one generic artifact contribution without mutating the native plugin or another artifact namespace.
- Preserve exact native scope and router ownership across verified plugin maintenance.
- Isolate complete adapter and router-owned state beneath an explicit destination for deterministic tests.
- Translate native command/process outcomes into stable domain records and typed errors.

**Non-Goals:**

- Defining a universal plugin manifest or converting a plugin between agents.
- Mutating native component enablement; native hosts remain responsible for component runtime behavior.
- Parsing or evaluating domain-specific artifact semantics such as ZPP trait frontmatter, `when` conditions, replacement, overlays, or composition.
- Publishing, authoring, validating, or submitting plugins and marketplaces.
- Adding, updating, or removing native marketplace and package sources.
- Treating plugins as dedicated filesystem projections governed by the existing skill/hook ownership manifest.

## Decisions

### Keep plugin records native-reference-first

The normalized `PluginRef` will retain the selected agent, opaque native reference, exact native scope, and source or catalog qualifier needed to address the installation without guessing. Common record metadata includes name, versions, installed state, activation evidence, and canonical runtime root. Agent-specific details may be carried as typed optional data, but a missing field remains unknown.

This avoids lossy coercion between `plugin@marketplace`, Kimi plugin ids and URLs, and Pi `npm:`, `git:`, or local source specs. A name-only universal id and common-denominator scope were rejected because they are ambiguous across marketplaces, source types, and coexisting native scopes.

### Keep remote discovery explicit and source administration deferred

Ordinary discovery reads installed state only. Available discovery is an explicit request and queries only catalogs or package sources already configured in the selected native agent. The router neither searches unconfigured public galleries nor adds, refreshes, or removes source registrations in this change.

### Isolate plugin adapters from asset projection utilities

Plugin discovery and lifecycle belong behind dedicated adapters rather than `utils.destinations`, `utils.mutation`, or the skill/hook ownership record. Native plugin managers own multiple locations and may execute dependency or authentication flows, so presenting the operation as a single copied destination would be false.

Shared process execution, JSON decoding, and result normalization can remain utility work if utility planning proves they are reusable. Agent policy and command construction stay in agent-specific plugin adapters.

### Preserve capability-owned verification targets

Discovery behavior, mutation behavior, and public command/library wiring will use separate feature roots and step bindings. This continues the repository's cache-ready target organization and prevents a single plugin feature from becoming the execution list for every behavior.

### Do not weaken native policy

The router will translate policy failures but will not bypass administrative restrictions, dependency rules, trust requirements, or native scope constraints. Any explicit router-level trust option must add caller authorization; it cannot override a native denial.

### Return canonical materialized paths without reconstructing them

Every installed record will expose the canonical absolute path from which the selected agent actually loads the plugin or package. Adapters SHALL prefer a host-reported runtime root. When the host reports only authoritative identity, version, or source fields, an adapter may derive the root through that agent's verified native layout, but it may not infer installation or activation from directory or cache presence. It SHALL verify that a returned root is absolute and materialized. An available-only catalog entry has no runtime root and therefore returns an unknown path rather than a predicted cache location.

Artifact resolution derives canonical absolute paths from that verified root and rejects traversal or symbolic-link resolution outside it. This gives callers a usable resolution contract without confusing a source checkout, marketplace record, or download cache with the effective runtime bundle.

### Preserve activation as evidence, not a universal Boolean

The normalized record will carry host-reported activation evidence and a normalized state of `enabled`, `disabled`, `partial`, or `unknown`. Codex, Claude Code, and Kimi can normally produce plugin-level `enabled` or `disabled`. Pi may produce `partial` when resource filters select only some native content, and the router SHALL NOT claim a package-level disabled Boolean that Pi does not provide.

An installed Pi package is eligible for generic artifacts under inherited router policy because Pi has no package-level disabled switch. Its resource filtering remains represented as partial or unknown native evidence rather than being discarded or promoted into a false package Boolean.

### Use explicit generic-artifact registrations

The generic extension seam follows the established OpenLease pattern: the host explicitly supplies an extension implementing an interface with `ArtifactManifest(identifier, contract_version)` and a locator; it does not scan for or execute arbitrary extension code. The locator receives an immutable `PluginArtifactContext` and returns relative candidates. The router resolves and validates canonical absolute results within the authoritative plugin root.

`agent-router` owns native discovery, plugin eligibility, and safe absolute-path resolution. A thin consumer extension owns domain parsing and composition. For ZPP, that means the extension may identify a conventional `traits/` artifact root while ZPP continues to validate trait documents and evaluate trait-specific activation, replacement, overlays, and composition.

### Overlay generic artifact policy without enabling plugins

Router policy is `inherit`, `enabled`, or `disabled`. It gates one artifact identifier for one stable scoped plugin reference and never writes native plugin state. Native disabled or uninstalled state always wins. `disabled` suppresses only that artifact namespace; `enabled` permits it only when the plugin is otherwise eligible; clearing an override restores `inherit`.

Explicit overrides are keyed by agent, exact native scope, native plugin reference, and artifact identifier without version or runtime root. This lets a user preference survive plugin updates and moves while fresh resolution follows the newly authoritative absolute path. Status reports both the requested policy and effective state with a reason so callers can distinguish native disablement, router disablement, eligibility, and absence.

### Verify native lifecycle postconditions

Native managers own dependency, authentication, cache, and policy semantics, so mutation adapters delegate only to supported noninteractive native surfaces and never edit registry files as a fallback. Preflight prevents known-invalid operations before invocation. After invocation, authoritative rediscovery proves the requested postcondition; process success alone is insufficient. If the manager may have changed state but rediscovery cannot verify convergence, the router reports that uncertainty rather than a false success.

Lifecycle verification remains intentionally narrower than artifact resolution. It may verify native identity, version, scope, root, and activation evidence, but it does not locate or load registered artifacts. Kimi lifecycle remains unsupported until Kimi exposes a supported noninteractive surface; read-only discovery may still consume its documented authoritative installed state.

### Restrict destructive lifecycle to router ownership

A verified install creates a router ownership receipt for the stable scoped `PluginRef`. Update and removal require that receipt and reject other discoverable native installations as unmanaged. Receipts remain decodable independently from the current version and runtime root so an intact historical record can authorize an update after native state moves. Removal clears ownership only after authoritative absence is verified.

Configured native catalog installation is already an explicit user action and needs no additional router trust switch. Direct URL, Git, and local executable sources require explicit trust before invoking the native manager. Router trust adds caller authorization but never overrides native policy.

Update remains single-plugin. Codex refreshes only the configured marketplace owning the selected plugin when current metadata is required, then converges only that plugin; bulk marketplace or plugin update is not part of this change.

### Treat destination as a complete adapter environment

The public `--destination` option and immutable library `AgentEnvironment` select the complete isolated root used by an adapter and router-owned state. All native registry, cache, runtime, receipt, and artifact-policy paths for that operation derive through the selected environment, and default user state is untouched. The option does not force an arbitrary plugin runtime folder outside native layout.

## Risks / Trade-offs

- **[Native CLI output changes]** → Prefer documented JSON modes where available, pin fixture contracts in adapter tests, and convert unrecognized output to a typed operational failure.
- **[No uniform Kimi programmatic command]** → Keep mutation unsupported rather than pretending the TUI slash command is a subprocess API or directly editing native state.
- **[Pi public discovery lacks a native CLI search command]** → Do not search its public gallery; available discovery stays within configured native sources.
- **[Pi has no package-level enabled flag]** → Preserve resource-level evidence and use installed-package eligibility for inherited generic-artifact policy.
- **[Plugins execute arbitrary code]** → Require explicit trust for direct URL, Git, and local sources while preserving native policy.
- **[Agent versions expose different capabilities]** → Detect capability support and return deterministic unavailable/unsupported outcomes rather than silently changing strategies.
- **[Updates can move catalog state]** → Key ownership and artifact policy to stable scoped references, refresh only the selected Codex marketplace, and re-resolve the resulting root.
- **[Native manager partially changes state]** → Re-discover authoritative state and report indeterminate or partially changed outcomes instead of claiming rollback or convergence the router cannot prove.

## Migration Plan

This is additive. Existing skill and hook APIs, CLI commands, ownership manifests, and destinations remain unchanged. Plugin contracts can be added behind new modules and commands, then removed without migrating existing skill/hook state if rollout is reversed.

## Clarification Gate

The owner confirmed the complete product boundary, including the generic-artifact interface and activation overlay. No outcome-changing clarification branch remains; the change is ready for feature shaping.
