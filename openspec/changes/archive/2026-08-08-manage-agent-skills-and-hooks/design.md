## Context

See `proposal.md` for motivation and scope. The target repository currently contains only a minimal Python package and console-script declaration. The migration source in ZPP separates skill projection, ownership manifests, inspection, preflight planning, filesystem mutation, native hook reconciliation, and CLI orchestration, but it also couples global installation to ZPP profiles and generated OpenSpec skills.

The four target agents share directory-based Agent Skills conventions. Their hook surfaces differ more substantially: Kimi stores user hook rules in TOML, Claude Code and Codex expose user and project structured hook configuration, and Pi implements user and project hook-equivalent behavior through TypeScript extensions. Kimi does not provide a native project hook surface in the accepted first-release matrix.

## Goals / Non-Goals

**Goals:**

- Keep a small package boundary with no dependency on the ZPP runtime.
- Provide a CLI-independent importable library and an optional Typer application.
- Isolate agent-specific paths and configuration formats behind adapters.
- Retain ownership-aware, idempotent, preflighted mutation and rollback behavior from the proven ZPP design.
- Make lifecycle operations usable from unattended `uvx` invocations on Windows, macOS, and Linux.

**Non-Goals:**

- Do not move ZPP's bundled workflow content into `agent-router`.
- Do not manage profiles, traits, OpenSpec generation, codespaces, agent plugins, or general agent settings.
- Do not make installed skills or hooks responsible for destination selection or ownership policy.

## Decisions

### Separate lifecycle core from agent adapters

Use one core planning and mutation boundary for validation, ownership, conflict classification, idempotence, and rollback. Agent adapters provide native destinations plus skill and hook encoding/reconciliation behavior.

This retains the strongest reusable part of ZPP while preventing a growing conditional tree in the CLI. Directly copying ZPP's workflow service was rejected because it would also import ZPP-only profile and OpenSpec policy.

### Load, validate, and copy source-native assets

Each installation operation loads one existing local skill directory or hook artifact. Loading validates the source structure and content without mutating an agent destination, identifies the agents whose native asset format is compatible, and fails explicitly when the format is malformed or ambiguous.

Installation prefers an unchanged copy or native entry reconciliation for an already compatible asset. Skills have no converters in the first release. Hooks have exactly two conversion directions: Claude Code to Codex and Codex to Claude Code. Both operate only on dedicated hook configuration files containing events common to both agents, command handlers, and the shared matcher, command, and timeout fields. Any unsupported event, handler type, or field rejects the whole conversion rather than being dropped.

Conversion is disabled by default and runs only when the caller authorizes it for that operation with `allow_conversion=True` in the library or `--allow-conversion` in the CLI. The converted document must pass the target adapter's validation before planning destination mutation. This guarantees configuration structure and the supported event/matcher/command mapping, not semantic equivalence of an opaque external script against both agents' runtime payloads. No adapter attempts static script analysis, a best-effort translation, Kimi TOML conversion, or Pi extension code generation.

For a dedicated native asset path, source-native projection is a file or directory copy. For a shared native configuration file, projection reconciles only the loaded owned entries into the existing document; “copy” never authorizes replacement of unrelated configuration.

A universal normalized hook-event model was rejected because it would reduce the product to the intersection of four changing hook systems and turn adapters into policy-heavy code generators. Package manifests, multi-asset workflow bundles, remote fetching, and registry resolution were deferred because the accepted first release begins from one caller-supplied local asset.

Automatic conversion was rejected because selecting a target agent does not itself authorize transformation of the supplied asset. Broader conversion was rejected because Kimi's flat TOML semantics and Pi's executable extension model do not fit a safe file-format translation. Claiming hook-script semantic verification was rejected because configuration conversion cannot prove arbitrary program behavior.

### Enforce one-way package ownership

Organize the source package around these ownership boundaries:

```text
src/agent_router/
├── __init__.py       # supported library exports
├── core/             # lifecycle contracts and orchestration
├── utils/            # reusable implementations matured through utility TDD
└── cli/              # optional Typer application and presentation
```

Imports flow from `cli` into the supported library/core surface and from core into accepted utilities. Core and utility modules never import the CLI package or Typer. The base package therefore remains importable when the `cli` extra is absent, while `agent_router[cli]` supplies Typer and the console application.

Placing the Typer application at the package root was rejected because importing the library could then fail when optional CLI dependencies are absent. Defining core contracts in utility modules was rejected because it would reverse ownership and make reusable implementations define the product boundary.

The later `zpp-plan-utilities` stage will decide the concrete contents of `utils/` from the approved feature set. This design fixes the directory's responsibility without preselecting utility functions or dependencies before that gate.

### Bind one agent to each public router instance

The initial library surface uses Python naming and an agent-bound object:

```python
router = AgentRouter(Agent.CODEX)
result = router.install_skill(
    Skill.from_path(source),
    destination=destination,
)
```

`AgentRouter` construction selects the adapter but performs no filesystem mutation. `Skill` owns asset identity and source content rather than agent policy. Lifecycle methods own validation and orchestration, return immutable structured results, and raise typed domain errors. The optional CLI translates arguments into these public calls and translates their results and errors back into process output and exit status.

Each CLI invocation likewise accepts exactly one agent. Callers needing multiple agents loop through independent library instances or command invocations. This intentionally removes cross-agent atomicity from the first release.

Camel-case method names were rejected because this is a Python library. Exposing adapter implementations directly was rejected because native encoding and path policy must remain replaceable internals. Batch constructors, iterable agent arguments, and multi-agent transactions were deferred because they would expand the mutation and rollback boundary without being necessary for agent resolution.

### Use inspect, install/reconcile, and uninstall lifecycle verbs

Expose read-only `inspect`, mutating `install`, and ownership-safe `uninstall` operations for skills and hooks. Installation converges an intact projection already owned by `agent-router`, so a separate update operation would duplicate the planner. Uninstallation is addressed by stable asset name plus the bound agent, semantic scope, project root, and optional destination; it does not require the original source path.

Installation listing is deferred because discovering installations across every native and overridden root requires an indexing contract beyond the exact destination lifecycle. A standalone update verb was rejected because it could diverge from idempotent installation semantics.

### Plan before mutating

Build and validate a complete mutation plan for each operation before writing its affected destination. Apply changes with atomic file replacement and rollback-aware directory creation/removal.

Best-effort copy/delete was rejected because hook files are shared configuration surfaces and an interrupted operation could otherwise corrupt unrelated agent setup.

### Prove ownership with content identity

Record enough installation identity to distinguish an intact projection installed by `agent-router` from a same-named unmanaged or user-modified asset. Uninstallation consumes that evidence and removes only content whose origin ownership and current installed identity both match. A source that was copied by another tool, even if byte-identical, is not considered owned. The source path is not required after installation.

Directory-name ownership was rejected because skills and extensions commonly share native roots with user-authored content. Blind overwrite or removal would violate the lifecycle contract.

### Use the settled Codex user-global skill root

The Codex adapter uses `~/.codex/skills` for user-global skill projection. The owner confirmed this as the product's settled location, consistent with the latest runtime-verified ZPP decision, so `agent-router` does not redirect that scope to the shared `~/.agents/skills` root.

Treating current external documentation as sufficient to reverse the established location was rejected because explicit owner correction is authoritative for this product boundary.

### Resolve explicit user and project scopes

The first release defaults to user-global scope and exposes repository-local scope explicitly. Skills support both scopes for all four agents. Hooks support both scopes for Claude Code and Codex, user scope only for Kimi, and both scopes for Pi hook-equivalent extensions. User scope resolves from the selected agent and host environment. Project scope additionally requires an explicit project root, which the selected adapter canonicalizes before resolving that agent's native repository-local asset surface. The router never depends on the process working directory to determine which repository a mutation targets.

Project scope does not authorize `agent-router` to invent a configuration convention. When the selected agent and asset type have no native repository-local surface, the library raises a typed unsupported-scope error and the CLI reports the equivalent deterministic failure without mutation.

Treating `--destination` as project scope was rejected because an arbitrary test or automation path does not express native agent semantics. General repository initialization was rejected because this package resolves and manages agent assets rather than bootstrapping unrelated project configuration.

### Route explicit destinations through the production planner

Inspect, install, and uninstall operations expose `destination` in the library and `--destination` in the CLI as a public override of the agent adapter's normal resolved physical target. The override enters the same inspection, planning, ownership, and mutation pipeline as a native destination; it does not activate a test-only filesystem implementation. Scope remains semantic metadata, and project scope still requires `project_root` even when a destination is supplied.

Keeping destination substitution solely as an internal test injection was rejected because the owner selected a public command parameter. Bypassing the production planner for custom paths was rejected because BDD would then exercise different safety behavior from real installations.

### Keep the command deterministic and optional

The optional Typer package exposes `skill inspect|install|uninstall` and `hook inspect|install|uninstall`. It presents human-readable output by default and a stable JSON envelope under `--json`, writes results to stdout and diagnostics to stderr, and never prompts for agent selection or uninstall confirmation. Exit statuses are `0` for success/no-op, `2` for invalid or unsupported requests, `3` for ownership or destination conflicts, and `1` for unexpected operational failures.

The base library does not import Typer. If the optional command surface is reached without the `cli` extra, a small dependency boundary reports that `agent_router[cli]` is required instead of leaking an import traceback. Adapter operation does not probe for or require an installed agent executable because filesystem setup may precede agent installation.

Interactive fallbacks were rejected because they make unattended `uvx` behavior depend on terminal availability. Requiring the native agent executable was rejected because it is unrelated to validating and projecting native filesystem assets.

### Reject symbolic links in source assets

Reject a symbolic link at the source root or anywhere beneath a copied skill or hook artifact. Validation does not follow the link. This keeps containment, cross-platform copying, content identity, and later ownership-safe removal deterministic in the first release.

Dereferencing links was rejected because it can copy content outside the selected asset. Preserving links was rejected because target behavior and Windows permissions vary and a link can later retarget without changing the ownership record.

### Split behavioral and functional verification

Use Behave scenarios to drive externally observable lifecycle behavior through the public command boundary. Use pytest in fail-first TDD for focused pure functionality such as path resolution, manifest and content identity, conflict classification, adapter reconciliation, and mutation planning. Keep reusable setup helpers outside step bindings without moving feature assertions into support modules.

Testing every parser or utility edge through the CLI was rejected because it obscures the behavior contract and makes failures less local. Testing adapter integration only through isolated units was rejected because path selection, native reconciliation, and transaction behavior must also be proven together.

The pytest boundary SHALL also prove that the base distribution imports without the `cli` extra and that core and utility modules do not acquire a transitive Typer dependency. Behave runs the optional installed CLI surface rather than importing Typer from test support.

### Keep ZPP integration as a downstream migration

Build `agent-router` as an independent product first. Replacing ZPP's internal utilities or changing ZPP commands is a later change in the ZPP repository after this package has an accepted and verified public contract.

This avoids making two repositories' behavior change atomically and keeps rollback to ZPP's current implementation straightforward.

## Risks / Trade-offs

- **[Risk] Agent conventions change independently** → Keep all paths and encodings in focused adapters and verify them against current first-party documentation during implementation.
- **[Risk] A limited converter drifts from a target agent's native format** → Keep each converter explicit, validate its output with the target adapter, and fail unsupported conversions without a fallback translation.
- **[Risk] Ownership metadata becomes stale after manual edits** → Fail closed and report the exact ambiguous path; never infer ownership from a name alone.
- **[Risk] Shared configuration rollback is difficult after concurrent external edits** → Re-read and verify expected pre-mutation identity immediately before atomic replacement.
- **[Risk] A custom destination escapes the usual agent root** → Treat the caller's exact path as explicit authority for only that invocation while retaining canonicalization, parent validation, conflict checks, and ownership-safe removal.
- **[Risk] A converted command invokes agent-specific script behavior** → Guarantee only the accepted configuration mapping, document the caller-owned script boundary, and reject every non-portable configuration field.
- **[Risk] Ownership evidence is copied or forged** → Bind ownership records to the package identity, addressed asset, destination, and installed content identity, and still fail closed on ambiguity.
- **[Risk] Optional CLI imports leak into the base library** → Enforce one-way package imports and verify the base installation in an environment without the `cli` extra.
- **[Trade-off] Independent extraction initially duplicates some ZPP logic** → Accept temporary duplication until ZPP deliberately migrates to the new package in its own product change.

## Migration Plan

1. Implement and release the standalone lifecycle without changing ZPP.
2. Verify equivalent ZPP-owned skill and hook fixtures through the new package plus the added Kimi adapter.
3. Open a separate ZPP change to replace its reusable lifecycle internals while retaining ZPP-specific orchestration and public commands.
4. Remove duplicated ZPP utilities only after ZPP's complete behavior suite is green against the new dependency.

Rollback consists of reverting the later ZPP dependency migration; installed assets remain governed by the ownership metadata and uninstall contract of the version that created them.
