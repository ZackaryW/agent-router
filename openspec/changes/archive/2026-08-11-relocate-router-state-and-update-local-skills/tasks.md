## 1. Prove scoped state behavior

- [x] 1.1 Add failing unit and lifecycle scenarios for user, project, custom-destination, and isolated-environment state resolution outside native agent surfaces.
- [x] 1.2 Implement collision-safe `.z-agent-router` state-root and ownership-record resolution while retaining complete record identity validation.
- [x] 1.3 Add failing migration scenarios for legacy-only, identical duplicate, divergent duplicate, malformed, empty-directory cleanup, and rollback states.
- [x] 1.4 Implement dual-read/current-write ownership migration for skills and hooks without mutating during inspection.
- [x] 1.5 Move plugin receipts and artifact-policy overrides to the selected scoped state root with legacy decoding and isolated `AgentEnvironment` coverage.

## 2. Mature complete-target replacement

- [x] 2.1 Add fail-first mutation tests for staging a complete directory, removing stale files, preserving a stable target path, and restoring the old target after each injected failure boundary.
- [x] 2.2 Extend the mutation utility to stage a validated complete projection and recover target, ownership, legacy-state, and auxiliary-file changes as one update outcome.
- [x] 2.3 Verify hidden native-adjacent staging is removed after success and rollback without promising the absence of transient watcher events.

## 3. Mature Git-ignore policy

- [x] 3.1 Add a validated public Git-ignore policy model for exact, pattern, and none modes, including the one-pattern cardinality rules.
- [x] 3.2 Add failing tests for exact state and target rules, existing glob coverage, effective negation, valid and ineffective explicit patterns, unrelated-byte preservation, unavailable Git, missing worktree, and none mode.
- [x] 3.3 Implement containing-worktree discovery, effective Git ignore evaluation, minimal `.gitignore` mutation, post-write verification, and rollback integration.

## 4. Wire project skill update

- [x] 4.1 Add lifecycle scenarios for modified, unmanaged, identical, absent, unsafe, explicit-destination, and failure-rollback project update targets while retaining user-scope conflict behavior.
- [x] 4.2 Implement `AgentRouter.update_skill` as a project-only existing-target operation that validates source and target before authoritative complete replacement.
- [x] 4.3 Export the validated update and Git-ignore contracts from the base library without importing CLI-only dependencies.
- [x] 4.4 Add `agent-router skill update` with explicit project scope, project root, optional destination, ignore policy and pattern validation, human output, JSON output, and deterministic errors.

## 5. Integrate and verify

- [x] 5.1 Update lifecycle and command documentation with scoped state locations, legacy migration, project update authority, and exact/pattern/none examples.
- [x] 5.2 Run capability-owned BDD, complete unit tests, CLI-extra verification, and Python 3.11 compatibility checks for every affected public surface.
- [x] 5.3 Record the separate ZPP consumer handoff: local workflow update must call `update_skill`, while global maintenance continues ownership-safe install/reconcile; do not add projection policy to ZPP in this repository.
