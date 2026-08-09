## 1. Clarification Gate

- [x] 1.1 Settle every item in `proposal.md` under `Unresolved — Do Not Assume` before feature shaping or implementation.
- [x] 1.2 Reconcile the accepted decisions into the proposal, all three capability deltas, design, and remaining task breakdown, then strictly validate the change.

## 2. Plugin Discovery Capability

- [x] 2.1 Shape plugin inventory, activation evidence, canonical runtime-root resolution, and generic-artifact resolution as capability-owned Behave features and cacheable affected-verification targets.
- [x] 2.2 Develop normalized plugin records, non-lossy activation states, authoritative installed-state decoding, canonical absolute root validation, and the confirmed agent discovery adapters through fail-first unit tests.
- [x] 2.3 Develop explicit namespaced artifact registration, immutable plugin contexts, relative-candidate containment, absolute artifact-path resolution, persisted policy overrides, and effective status reasons through fail-first unit tests.
- [x] 2.4 Wire read-only library and CLI discovery behavior and prove the complete discovery and artifact-resolution features.

## 3. Plugin Lifecycle Capability

- [x] 3.1 Shape plugin installation, single-plugin update, and removal as a capability-owned Behave feature and affected-verification target.
- [x] 3.2 Develop supported native lifecycle adapters, exact native scope handling, ownership receipts, direct-source trust preflights, single-plugin update, authoritative postcondition verification, policy/error translation, and deterministic converged, unsupported, unmanaged, indeterminate, and partially changed results through fail-first unit tests.
- [x] 3.3 Prove that Kimi mutation never falls back to direct-state editing and that lifecycle verification never resolves or caches generic artifacts.
- [x] 3.4 Wire the complete lifecycle behavior without changing skill/hook ownership or destination semantics.

## 4. Programmatic Command Surface

- [x] 4.1 Add the confirmed agent-bound Python, `AgentEnvironment`, `PluginRef`, artifact-extension, policy, status, and resolution contracts while keeping the base library independent of CLI-only dependencies.
- [x] 4.2 Add `plugin discover`, lifecycle, artifact-status, and artifact-policy Typer commands with `--available`, exact scope, direct-source trust, `--destination`, and stable human and JSON outcomes.
- [x] 4.3 Prove command/library parity and deterministic unavailable, unsupported, policy, and operational failures.

## 5. Integrated Verification

- [x] 5.1 Run capability-owned Behave targets, the full Behave audit, and complete pytest suite on the supported Python floor.
- [x] 5.2 Verify isolated native-agent fixtures covering stale caches, moved roots, persisted artifact overrides, default-state non-access, false-success process exits, partial native mutation, direct-source trust, unmanaged mutation rejection, and global-versus-local root separation; build the GitHub-installable library and CLI extra; and strictly validate OpenSpec before checkpointing.
