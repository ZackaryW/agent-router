## Why

Router ownership records currently live beneath native agent discovery and configuration roots. Agent applications can observe or touch those `.agent-router` directories, producing false skill entries and ownership conflicts, while repository-local maintenance has no explicit operation for replacing a disposable local skill projection from its authoritative source.

## What Changes

- Move persistent router-owned state out of native agent surfaces into `~/.z-agent-router` for user scope and `<project>/.z-agent-router` for project scope, including skill and hook ownership plus plugin receipts and artifact-policy overrides.
- Read valid legacy native-relative `.agent-router` state during migration, publish current state at the scoped root on the next authorized mutation, and remove only proven obsolete empty router directories.
- Add an explicit project-scope skill update operation that atomically replaces the complete existing target projection at the same resolved path from validated source content. Local update accepts modified or unmanaged target content as replacement-authorized, while user-scope installation and reconciliation remain ownership-safe.
- Make project update require an existing exact target, retain byte-identical updates as no-ops, reject unsafe target structures, and preserve unrelated sibling skills and shared native configuration.
- Have project update maintain repository ignore behavior by default. Exact per-skill ignore is the default; callers may request a supplied glob pattern or disable ignore mutation. Existing effective Git ignore coverage, including glob and negation behavior, is authoritative and shall not receive redundant entries.
- Expose the update and ignore policies through the importable Python API and optional noninteractive CLI.
- Require a separately owned downstream ZPP change to make local workflow update call the new Agent Router update surface; global ZPP maintenance continues using ownership-safe installation reconciliation.

## Capabilities

### New Capabilities
- `router-state-storage`: Defines scoped persistent router state outside native agent surfaces, isolated environment behavior, and safe migration from legacy relative state.

### Modified Capabilities
- `agent-skill-lifecycle`: Adds explicit authoritative full replacement for existing project-local skill projections while preserving current user-scope ownership safety.
- `agent-plugin-lifecycle`: Reconciles plugin receipts and artifact-policy persistence with the shared scoped router-state location and isolated adapter environments.
- `programmatic-command-surface`: Adds the project-local skill update method and command plus exact, pattern, and disabled Git-ignore policies.

## Impact

- Affects ownership and plugin-state path resolution, lifecycle planning, atomic mutation, legacy-state cleanup, project Git-ignore handling, public library exports, Typer commands, structured results, tests, and documentation.
- Changes persistent state locations and therefore requires compatibility reads and verified migration rather than a flag-day move.
- Introduces Git-aware behavior only for project-local update ignore policy; user-scope lifecycle remains independent of a repository.
- Requires a separate coordinated consumer change in ZPP so local workflow update selects the new replacement operation without moving projection authority into ZPP.

## Unresolved — Do Not Assume

- None. The owner has selected scoped `.z-agent-router` state, project-only authoritative replacement, exact-per-skill ignore by default, explicit glob adherence, and an option that disables Git-ignore mutation.
