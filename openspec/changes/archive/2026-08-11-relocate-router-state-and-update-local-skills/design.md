## Context

Skill and dedicated-hook ownership records are currently placed under native destination roots, shared-hook records are placed beside native configuration, and plugin state is placed in a relative `.agent-router` directory beneath its selected environment. These locations make persistent router bookkeeping visible to agent scanners and application watchers. The current skill lifecycle also has one install/reconcile method: it safely updates only an intact owned projection and intentionally rejects modified or unmanaged content, including in project scope.

The owner has selected a different local model. User state is machine-scoped beneath `~/.z-agent-router`; project state is clone-scoped beneath `<project>/.z-agent-router`; project update is explicit authority to replace one complete existing target; and managed Git-ignore behavior keeps local state and projections out of version control unless disabled. Canonical OpenSpec remains authority for existing user-scope safety. Relevant temporal history adds two migration constraints: historical ownership decoding must not depend on current inventory, and repository-local behavior must remain explicitly selected rather than becoming the global default.

## Goals / Non-Goals

**Goals:**

- Remove persistent router bookkeeping from all native agent discovery and configuration surfaces.
- Resolve collision-safe user, project, and isolated-environment state roots.
- Migrate valid legacy records without turning inspection into mutation or losing rollback.
- Add a first-class local skill update that stages and replaces one complete target at a stable path.
- Use effective Git ignore semantics for exact, explicit-pattern, and disabled policies.
- Preserve user-scope ownership safety and keep downstream ZPP orchestration thin.

**Non-Goals:**

- Adding authoritative replacement to user-global skill maintenance.
- Adding hook update commands or replacing whole shared native configuration files.
- Automatically adopting or deleting malformed, divergent, or unprovable legacy state.
- Eliminating every transient filesystem event produced by an atomic native-target swap.
- Moving Git-ignore or native destination policy into ZPP.

## Decisions

### Resolve one scoped router-state root

`AgentRouter` will resolve state independently from native destinations. Normal user scope uses `home / ".z-agent-router"`; project scope uses `project_root / ".z-agent-router"`; and an explicit isolated plugin environment derives the equivalent router state beneath that environment. Destination overrides do not relocate state because scope, not physical target adjacency, owns persistence.

State will remain record-oriented rather than becoming one shared database. Ownership paths will include agent, kind, a digest of the canonical destination, and validated asset identity. Records retain the unhashed canonical destination and complete identity for collision and forgery checks. Plugin receipts and artifact-policy overrides live at the same scoped root while retaining their existing independently decodable schema.

Storing everything under the user root was rejected for project scope because clone-local replacement and ignore policy need clone-local lifecycle state. Keeping state inside each native destination was rejected because that is the observed source of app conflicts.

### Use dual-read and current-write migration

Inspection resolves current state first and falls back to the exact legacy path only when current state is absent. It never migrates during inspection. If both records exist, only identical validated evidence is acceptable; divergence fails closed. An authorized mutation writes or consumes current state and removes the legacy record in the same recoverable mutation. Cleanup walks only the known legacy router directories and removes a directory only after proving it empty.

A flag-day move was rejected because every existing installation would become unmanaged. Blindly preferring either duplicate record was rejected because copied or stale evidence could authorize the wrong projection.

### Add a distinct project update operation

`update_skill` and `skill update` are separate from install/reconcile because they carry materially different authority. The operation is project-only, requires an existing exact target, and authorizes replacement of modified or unmanaged content at that target. User-scope install continues to require intact ownership.

The update planner validates source and target safety, stages the complete new directory as a hidden sibling on the target filesystem, and then swaps the staged directory into the stable target path while retaining the old target for rollback. It writes current ownership and any requested Git-ignore change within the same recoverable plan. Complete staging prevents stale-file merging and avoids exposing a successfully completed partial target; the target inode need not remain stable.

Inferring replacement authority from every project-scope install was rejected because an ordinary install could then erase a user-authored skill. Public uninstall-followed-by-install was rejected because it creates a gap, loses rollback scope, and cannot authorize unmanaged input safely.

### Treat Git ignore as an explicit update policy

The public policy has three values: `exact`, `pattern`, and `none`. Exact is the default and ensures effective ignore coverage for the project `.z-agent-router` path plus only the selected skill target. Pattern requires one caller-supplied Git ignore pattern for the target while state remains covered. None bypasses Git detection and ignore-file access entirely.

For exact and pattern, the planner finds the containing worktree, evaluates current effective coverage with Git semantics, and avoids redundant entries when an existing glob already covers a path. If a write is required, it preserves unrelated `.gitignore` bytes, applies the minimum new rules, verifies effective coverage including negation, and rolls the change back if verification or target replacement fails. A missing worktree, unavailable Git executable, malformed policy, ineffective pattern, or unmodifiable ignore file fails before target replacement.

Text-only matching was rejected because it mishandles glob coverage, nested rules, and negation. A broad agent-root glob as the default was rejected because it can hide user-authored skills. Automatically removing existing ignore entries under none policy was rejected because their ownership is not provable.

### Keep Agent Router authoritative across the ZPP boundary

The downstream ZPP local workflow update should call the new method and pass the selected ignore policy; global workflow maintenance continues calling ownership-safe install/reconcile. Agent Router continues to resolve native destinations, state, Git-ignore effects, and projection mutation. ZPP selects workflow assets and operation scope only.

## Risks / Trade-offs

- **[Risk] Explicit local update can destroy intentional local edits.** → Limit replacement to an explicit project update operation and exact target; validate source and target first; never infer this authority for install or user scope.
- **[Risk] A caller-supplied glob can hide unrelated repository content.** → Make exact the default, require pattern to be explicit and effective for the target, and report the applied policy.
- **[Risk] Split legacy and current state can become ambiguous.** → Validate both complete records, accept only identical evidence, and fail closed on divergence.
- **[Risk] State migration and target replacement span multiple paths.** → Stage complete content, retain backups until all writes and Git verification succeed, and exercise rollback failures at every boundary.
- **[Risk] Project state remains untracked and can disappear on clone cleanup.** → Treat it as local ownership evidence; an explicit local update can re-establish ownership, while uninstall still requires current proof.
- **[Risk] Native applications may observe transient hidden staging siblings.** → Keep staging hidden and short-lived; eliminating all watcher events is outside this change because same-filesystem replacement requires native-adjacent staging.
- **[Risk] Git becomes a conditional runtime dependency.** → Require it only for exact or pattern project update; none policy remains Git-independent, and all other lifecycle operations remain unchanged.

## Migration Plan

1. Add scoped state resolution and dual-read analysis while continuing to recognize every valid legacy receipt.
2. Route new user, project, and isolated-environment writes to `.z-agent-router` and make lifecycle mutations remove migrated legacy records transactionally.
3. Add complete-target staging, Git-ignore planning, and the project update library surface.
4. Add the CLI command and deterministic policy validation.
5. After this Agent Router change is available, hand off a separate ZPP change that calls project update for local workflow maintenance while leaving global reconciliation unchanged.
6. After compatibility coverage proves migration, retain legacy reads for the supported migration window; removal requires a later explicit change.

Rollback reverts callers to the prior package while leaving valid legacy records available until migration. Once a record exists only in `.z-agent-router`, rollback cannot safely invent legacy state; affected projections must continue with the new router or use an explicit verified migration utility rather than copying records blindly.

## Open Questions

- None.
