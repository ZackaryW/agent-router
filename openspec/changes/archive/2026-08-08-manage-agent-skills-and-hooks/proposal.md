## Why

Agent skill and lifecycle-hook installation is currently embedded in ZPP, which makes otherwise reusable agent integration logic depend on the larger ZPP product. Extracting that behavior into `agent-router` will provide an importable Python library plus an optional CLI that can be run through `uvx` and used by automation across Kimi Code CLI, Pi, Claude Code, and Codex.

## What Changes

- Add a non-ZPP-specific inspect, install/reconcile, and uninstall lifecycle for managed Agent Skills for Kimi, Pi, Claude Code, and Codex.
- Add the same lifecycle for managed native hooks or hook-equivalent integrations for the supported native agent scopes.
- Load one local skill directory or hook artifact per installation request, validate its content before mutation, and identify the agents for which the loaded asset is natively compatible.
- Prefer source-native projection: copy compatible skill content without translating it. Ship no skill conversions in the first release, and limit hook conversion to the portable command-hook subset shared by Claude Code and Codex.
- Keep conversion disabled by default and require explicit per-operation authorization through the library's `allow_conversion=True` argument or the CLI's `--allow-conversion` option.
- Publish the base `agent_router` package as an importable library whose core contracts do not require CLI dependencies.
- Expose an agent-bound Python API centered on `AgentRouter(Agent.CODEX).install_skill(Skill.from_path(...))`, with snake-case lifecycle methods, structured results, typed domain errors, and the same destination override available to library callers.
- Provide the Typer-based `agent-router` command when the package is installed with the `agent_router[cli]` extra, so callers can execute the lifecycle through `uvx` without interactive agent selection or confirmation.
- Keep each library router and CLI invocation bound to exactly one agent; multi-agent batching and cross-agent transactions are outside the first release.
- Support user-global scope by default and explicit repository-local scope, resolving each through the selected agent's native surface and rejecting a scope that the selected agent and asset type do not natively support.
- Let repository-local callers identify the repository with an explicit project root rather than relying on the process working directory.
- Allow inspect, install, and uninstall callers to replace the selected agent's normal resolved target with an explicit `--destination` path while retaining semantic scope, project-root, safety, and ownership rules.
- Preserve unrelated agent configuration and content, reject unmanaged conflicts, make compatible repeated installation a no-op/reconciliation operation, and remove only projections installed by `agent-router` whose current ownership and installed identity it can prove.
- Provide human-readable CLI output by default, stable JSON output for automation, deterministic exit categories, and actionable behavior when the CLI extra is absent.
- Reject symlinked asset roots and entries in the first release, and do not require an agent executable to be installed to manage its filesystem projection.
- Migrate the reusable destination, inspection, ownership-manifest, preflight, and filesystem-transaction behavior from ZPP without migrating ZPP workflow bundles, OpenSpec generation, profiles, trait resolution, codespaces, or other ZPP product policy.
- Add Kimi as a new adapter using its native skill and hook configuration surfaces.
- Use `~/.codex/skills` as Codex's settled user-global skill destination.

## Capabilities

### New Capabilities

- `agent-skill-lifecycle`: Inspect, install/reconcile, and uninstall owned skills safely across each supported agent's native user-global and repository-local skill scopes.
- `agent-hook-lifecycle`: Inspect, install/reconcile, and uninstall owned hook integrations in supported native scopes without overwriting unrelated native agent configuration.
- `programmatic-command-surface`: Invoke deterministic agent asset operations through the importable library or the optional packaged `agent-router`/`uvx` command and receive automation-appropriate outcomes.

### Modified Capabilities

None. `agent-router` has no existing canonical product specifications.

## Impact

- Affects the `agent-router` Python package, its importable API, optional CLI extra and console entry point, packaged metadata, tests, and documentation.
- Reuses concepts currently implemented under `zpp.utils.skill_*`, `zpp.utils.agent_hooks`, `zpp.utils.agent_bootstrap`, and their filesystem mutation support, but establishes independent ownership and naming for this package.
- Reads and mutates native agent skill directories and hook configuration under user homes and explicitly selected repository roots on Windows, macOS, and Linux.
- Requires agent-specific adapters because Pi uses TypeScript extensions for hook-equivalent behavior while Kimi, Claude Code, and Codex expose different configuration formats.

## Unresolved — Do Not Assume

None. Multi-agent batching, a separate update command, installation listing, additional conversion pairs, semantic verification of opaque hook scripts, and symlink support are explicitly deferred rather than left open for implementation-time choice.
