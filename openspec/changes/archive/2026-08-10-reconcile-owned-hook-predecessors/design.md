## Context

Agent Router currently recognizes a shared hook as managed only when its
ownership record and exact recorded fragment are both present. A caller cannot
declare an exact pre-ownership hook as the predecessor of a current asset, and
an intact ownership record whose fragment was completely removed is classified
the same way as a modified fragment. Component consumers therefore cannot
perform a safe normal repair without editing native files themselves.

Hook destinations differ: Claude Code and Codex share JSON settings, Kimi shares
TOML configuration, and Pi uses dedicated file or directory projections. Any
new contract must preserve unrelated native configuration, keep inspection
read-only, and retain per-destination atomic mutation.

## Goals / Non-Goals

**Goals:**

- Accept caller-supplied exact predecessor `Hook` assets during inspection and
  installation of one current hook.
- Distinguish exact predecessor, predecessor-plus-current, and wholly missing
  owned states from structural ambiguity.
- Reconcile recoverable states inside Agent Router and report their transition.
- Permit removal of stale ownership evidence when the owned projection is
  wholly absent.
- Expose the same bounded contract through the base Python API and optional CLI.

**Non-Goals:**

- Discovering predecessors from native files, command prefixes, versions, or
  caller-specific conventions.
- Adopting a partially modified predecessor or owned fragment.
- Giving one operation authority over multiple agents or destinations.
- Changing skill, plugin, or native-agent execution behavior.

## Decisions

### Use exact Hook assets as predecessor evidence

`inspect_hook` and `install_hook` accept a keyword-only immutable sequence of
validated `Hook` assets named `predecessors`. Passing an asset explicitly
associates it with the requested current logical hook; historical and current
asset names may differ because dedicated native layouts can rename projections.
Every predecessor must be natively compatible with the selected agent without
conversion, target the same resolved semantic scope, and be distinct by exact
fragment or projection identity.

The CLI exposes repeatable `--predecessor PATH` only for hook inspect/install.
It loads each path through `Hook.from_path` before destination inspection.
Agent Router never scans for candidate history. A caller-specific registry or a
command-prefix matcher was rejected because the component cannot prove either
as ownership.

### Reuse lifecycle status and add a separate transition enum

Recoverable inspection states use existing `outdated` status so callers that
already accept current/outdated hook convergence remain compatible. A new
`HookTransition` enum records `legacy-replaced`, `legacy-pruned`,
`owned-restored`, or `owned-removed`; ordinary operations use `None`.
`LifecycleResult.hook_transition` is serialized independently from `converted`,
which continues to mean cross-agent source conversion only.

Inspection maps exact predecessor-only, predecessor-plus-current, and
owned-missing states to `outdated` plus their transition. Installation returns
`updated` with the same transition. This was preferred over new top-level
ownership statuses because the states are operation-specific reconciliation
plans, not persistent ownership classes.

### Classify shared fragments with exact presence and structural overlap

Add a read-only fragment probe returning `present`, `absent`, or `conflict`.
`present` requires every expected native group or entry exactly once.
`absent` requires no exact group and no structural overlap. `conflict` covers a
partial fragment, duplicates, an exact recognized command in an unexpected
group, or an exact nonempty matcher at the same event with changed handlers.
Unrelated entries that share only an event remain unrelated.

Inspection probes the recorded owned fragment, current fragment, and every
predecessor against one validated destination snapshot. Exactly one predecessor
may participate. A current fragment plus one predecessor is recoverable; two
predecessors, partial overlap, invalid ownership, or competing current state is
a conflict.

Perfect recognition of arbitrary semantic edits is intentionally impossible:
the component relies only on exact caller evidence and conservative structural
overlap. Treating every group in the same event as related was rejected because
it would claim unrelated session hooks.

### Probe dedicated projections by exact target and fingerprint

For Pi file/directory hooks, each current and predecessor asset resolves its own
target beneath the selected destination. Exact bytes/tree fingerprint establish
presence. A missing current target with a valid ownership record is recoverable
only when no predecessor target partially occupies the same path and no
ambiguous sibling target is declared. Exactly one intact predecessor target may
be removed while the current target and ownership record are written atomically.

### Keep reconciliation and ownership publication in one mutation

Shared installation removes only exact recorded/predecessor fragments from the
validated in-memory document, reconciles the exact current fragment, and writes
the destination plus ownership record in one `MutationPlan`. Dedicated
installation deletes only the exact validated predecessor/current target being
replaced and writes the new projection plus ownership record in one plan.

Uninstall with a valid record and wholly absent owned projection deletes only
the ownership record and returns `owned-removed`. Partial or modified state
still raises `ConflictError`. Inspection and failed preflight never mutate.

## Risks / Trade-offs

- [A predecessor path is malformed or incompatible] -> Reject it before
  destination inspection or mutation.
- [Native state changes after inspection] -> Installation independently probes
  the current destination and fails if the bounded transition no longer holds.
- [A user intentionally removed an owned hook] -> Only explicit install repairs
  it; explicit uninstall removes the stale receipt; inspection remains read-only.
- [An edit avoids all exact structural overlap] -> It remains unrelated by the
  generic component contract; callers must not broaden predecessor evidence.
- [Result consumers assume a fixed JSON key set] -> Add the nullable transition
  field as an additive stable field and retain every existing status/flag meaning.

## Migration Plan

1. Add fail-first shared and dedicated probe/reconciliation tests.
2. Add the public predecessor parameter, transition enum, and serialized field.
3. Implement shared and dedicated inspection/install/uninstall transitions.
4. Add repeatable CLI predecessor loading and public import coverage.
5. Run unit, BDD, build, and strict OpenSpec verification before consumers pin
   the resulting commit.

Rollback removes the additive API. Already reconciled hooks remain ordinary
current Agent Router-owned projections and require no state migration.

## Open Questions

None.
