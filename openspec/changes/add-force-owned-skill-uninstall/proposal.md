## Why

Recovery tooling sometimes must remove a skill that Agent Router demonstrably installed even after its projected content drifted. The default uninstall correctly preserves modified content, but callers currently have no explicit no-history deletion authority for a proven-owned skill.

## What Changes

- Add an explicit `force=True` option to the Python `AgentRouter.uninstall_skill` contract.
- Require matching valid Agent Router ownership before forced deletion; never delete a same-named unmanaged target.
- Allow forced uninstall to remove modified or missing owned skill content together with its ownership state, without retaining a backup or history.
- Treat a wholly absent target and ownership record as an already-converged no-op.
- Preserve the current ownership-safe behavior as the default and add no command-line force option.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `agent-skill-lifecycle`: Adds explicit forced deletion for modified but proven-owned skill projections while preserving default uninstall safety.
- `programmatic-command-surface`: Adds the typed force option only to the importable library method.

## Impact

- Public Python API: `AgentRouter.uninstall_skill(..., force: bool = False)`.
- Mutation safety: forced deletion uses existing exact destination and ownership-state resolution and does not follow an unmanaged path.
- CLI: unchanged; `agent-router skill uninstall` continues to use default ownership-safe behavior.
- Tests and feature contracts cover modified owned content, absent convergence, unmanaged refusal, state cleanup, and default compatibility.

## Unresolved — Do Not Assume

None.
