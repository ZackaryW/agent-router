## Why

The hook lifecycle cannot currently recover when a caller upgrades from an
exact hook fragment it previously authored before Agent Router ownership, or
when a valid ownership record remains after its shared fragment was wholly
removed. Both states collapse into a generic conflict, forcing component users
either to perform unsafe native-file edits or to duplicate destination mutation
outside Agent Router.

## What Changes

- Accept explicit exact predecessor hook assets for inspection and installation
  of the same logical hook identity.
- Distinguish an intact owned fragment that is wholly absent from partially
  modified, duplicated, misplaced, or otherwise ambiguous hook state.
- Reconcile supported predecessor-only, predecessor-plus-current, and
  owned-missing states atomically while preserving unrelated native settings.
- Let uninstall discard stale ownership evidence when the exact owned fragment
  is wholly absent, without recreating the fragment first.
- Report a hook transition reason independently of the existing cross-agent
  source-conversion flag.
- Keep predecessor adoption explicit and exact; never infer ownership from a
  command prefix, destination, filename, event alone, or caller resemblance.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `agent-hook-lifecycle`: Add exact predecessor reconciliation, owned-missing
  repair/removal, structural ambiguity protection, and transition reporting.
- `programmatic-command-surface`: Expose predecessor inputs and hook transition
  evidence through the importable lifecycle without changing conversion
  semantics or requiring CLI-only dependencies.

## Impact

- Public hook lifecycle models and `AgentRouter` inspect/install/uninstall
  methods.
- Shared JSON/TOML hook reconciliation, dedicated hook projections, ownership
  classification, and atomic mutation planning.
- Structured lifecycle result serialization and optional hook CLI inputs where
  source paths are explicitly supplied.
- Hook, ownership, destination, mutation-failure, API, and CLI tests.
- No skill lifecycle, plugin lifecycle, native agent execution, or caller-
  specific hook semantics become part of Agent Router.

## Unresolved — Do Not Assume

None.
