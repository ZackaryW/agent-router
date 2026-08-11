## Context

Default skill uninstallation requires projected content to match its ownership fingerprint. ZPP reset needs a narrower recovery authority: delete a canonical skill that Agent Router demonstrably installed even after drift, retain no history, and never apply that authority to an unmanaged target.

The base library is ZPP's component boundary. The optional CLI remains conservative and does not expose force deletion.

## Goals / Non-Goals

**Goals:**

- Add typed forced deletion to the Python skill-uninstall API.
- Require matching valid ownership for every present target.
- Remove modified, missing, file, directory, or symbolic-link owned targets without following links.
- Remove ownership atomically with the target and treat wholly absent state as converged.
- Preserve default uninstall and CLI behavior.

**Non-Goals:**

- Force install/update, hook force deletion, unmanaged adoption, or a CLI force option.
- Backup, trash, audit history, or recovery storage after success.
- Weaker ownership validation or destination resolution.

## Decisions

### Make force explicit and library-only

`AgentRouter.uninstall_skill` accepts keyword-only `force: bool = False`. Default behavior is unchanged and the CLI omits the argument.

A separate method was rejected because force is one authorization mode for stable-name uninstall. A CLI flag was rejected because no additional human control surface is needed.

### Require matching ownership

Forced uninstall loads current and legacy evidence. A present target is eligible only when its record matches agent, skill name, scope-derived state, and exact destination. Malformed, divergent, mismatched, or absent ownership with present content remains a conflict. Fingerprint drift is ignored only after identity is proven. Valid ownership with missing content authorizes stale-state cleanup; no target and no record returns `absent`.

### Reuse atomic mutation with exact symlink authorization

`MutationPlan.allowed_symlink_replacements` defaults empty and must be a subset of replacements. Forced uninstall authorizes only its resolved target. The utility moves the link itself into rollback staging, never follows its target, and leaves ownership paths under default link rejection.

Direct recursive deletion, broad link permission, and a force-specific deletion utility were rejected because they bypass atomic validation.

### Retain no successful history

Successful mutation removes rollback staging, the target, and ownership records. Staging exists only in flight and restores on failure; no backup, tombstone, or receipt remains after success.

## Risks / Trade-offs

- **A caller chooses the wrong name** → Matching ownership at the resolved destination remains mandatory.
- **A target became a symlink** → Only the link is removed; its target remains unchanged.
- **Evidence is malformed or divergent** → Deletion fails closed for diagnosis.
- **Mutation fails** → Existing rollback restores target and state.
- **No history remains** → This is explicit authority for disposable projections only.

## Migration Plan

1. Add feature and mutation coverage.
2. Add exact symlink replacement authorization.
3. Bind force in the Python router while preserving default and CLI calls.
4. Bump and publish Agent Router 0.1.3.
5. Rollback removes force and exact link authorization; default behavior remains compatible.

## Open Questions

None.
