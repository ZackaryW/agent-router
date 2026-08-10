## 1. Specify Public Transition Evidence

- [x] 1.1 Add fail-first model and serialization tests for nullable `HookTransition` values while preserving `converted` semantics and existing lifecycle status behavior.
- [x] 1.2 Add `HookTransition` to the base public exports and extend `LifecycleResult` with additive transition evidence.
- [x] 1.3 Add fail-first API and CLI tests for immutable predecessor hooks and repeatable `--predecessor` loading on hook inspect/install only.
- [x] 1.4 Extend `AgentRouter.inspect_hook` and `install_hook` plus the optional CLI to accept and validate exact predecessor `Hook` assets.

## 2. Classify Shared Hook State

- [x] 2.1 Add fail-first JSON hook probes for exact presence, complete absence, partial groups, duplicate groups, misplaced exact commands, changed handlers under an exact nonempty matcher, and unrelated groups.
- [x] 2.2 Add equivalent fail-first Kimi TOML probe coverage for exact, absent, partial, duplicate, misplaced, and unrelated entries.
- [x] 2.3 Implement shared-fragment `present`/`absent`/`conflict` probing without command-prefix, filename, or event-only ownership inference.
- [x] 2.4 Add fail-first router tests for predecessor-only, predecessor-plus-current, multiple predecessors, owned-missing, current, outdated, and ambiguous shared destinations.

## 3. Reconcile Shared and Dedicated Hooks

- [x] 3.1 Implement shared inspection and atomic installation for legacy-replaced, legacy-pruned, and owned-restored transitions while preserving unrelated configuration.
- [x] 3.2 Add fail-first dedicated Pi file/directory tests for exact predecessor replacement, owned-missing restoration, partial targets, and differing historical target names.
- [x] 3.3 Implement dedicated predecessor/owned-missing inspection and atomic installation using exact target fingerprints.
- [x] 3.4 Implement owned-missing uninstall as stale ownership-record removal for shared and dedicated hooks while retaining conflicts for partial or modified state.
- [x] 3.5 Add mutation-failure tests proving destination and ownership publication remain atomic for every supported transition.

## 4. Verify and Publish the Component Contract

- [x] 4.1 Add BDD scenarios and bindings for predecessor replacement, predecessor pruning, owned restoration/removal, ambiguity rejection, and unrelated-content preservation.
- [x] 4.2 Update README/API examples for exact predecessor inputs and hook transition results without caller-specific migration guidance.
- [x] 4.3 Run unit tests, every BDD root, configured static checks, package build, and strict OpenSpec validation.
