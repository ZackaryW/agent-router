# agent-router

`agent-router` installs, inspects, reconciles, and uninstalls Agent Skills and
native hooks for Codex, Claude Code, Kimi Code CLI, and Pi.

It is an importable library first. The Typer CLI is optional.

## Install from GitHub

`agent-router` is installed directly from its GitHub repository; it is not
published to a package index. Python 3.11 or later is required.

```console
uv add "agent-router @ git+https://github.com/ZackaryW/agent-router.git"
uv add "agent-router[cli] @ git+https://github.com/ZackaryW/agent-router.git"
```

Run the CLI without installing it into a project:

```console
uvx --from "agent-router[cli] @ git+https://github.com/ZackaryW/agent-router.git" agent-router --help
```

Use `@<tag-or-commit>` after `.git` to pin a release or revision.

## Python

```python
from agent_router import Agent, AgentRouter, GitIgnorePolicy, Hook, Scope, Skill

router = AgentRouter(Agent.CODEX)
skill = Skill.from_path("./reviewer")

result = router.install_skill(skill)
print(result.status, result.destination)

router.uninstall_skill(skill.name)
```

Default uninstall preserves a managed skill whose projected content was
modified. Recovery tooling can explicitly discard a modified but still
proven-owned skill through the Python library:

```python
router.uninstall_skill(skill.name, force=True)
```

Forced uninstall still requires a valid matching Agent Router ownership record,
never deletes a present unmanaged target, removes the exact target without
following a symbolic link, and retains no backup or history after success. A
wholly absent target and ownership record is an `absent` no-op. The optional CLI
does not expose forced deletion.

Every router is bound to one agent. Operations use user scope by default;
project scope requires an explicit project root.

```python
router.install_skill(
    skill,
    scope=Scope.PROJECT,
    project_root="./repository",
)
```

Repository-local maintenance has a separate authoritative update operation. It
requires project scope, an explicit project root, and an already-existing exact
target. The validated source completely replaces that target, including removal
of stale files; modified or unmanaged local content is replaceable only through
this explicit operation. User-scope install remains ownership-safe.

```python
result = router.update_skill(
    skill,
    scope=Scope.PROJECT,
    project_root="./repository",
)

# Use an explicit repository glob, or bypass Git-ignore management entirely.
router.update_skill(
    skill,
    scope=Scope.PROJECT,
    project_root="./repository",
    ignore_policy=GitIgnorePolicy("pattern", "/.agents/skills/*/"),
)
router.update_skill(
    skill,
    scope=Scope.PROJECT,
    project_root="./repository",
    ignore_policy=GitIgnorePolicy("none"),
)
```

Exact per-skill ignore is the default. It ensures `.z-agent-router` and only the
selected skill target are effectively ignored, while honoring existing Git
globs and negations without adding redundant rules. Pattern mode requires one
effective pattern. None mode neither requires Git nor reads `.gitignore`.

Downstream workflow integrations should call `update_skill` only for explicitly
selected repository-local replacement. User/global reconciliation continues to
call ownership-safe `install_skill`; callers do not reproduce destination,
state, replacement, or Git-ignore policy outside Agent Router.

Hook inspection and installation may receive an immutable sequence of exact
native predecessor artifacts for the same selected agent and semantic scope.
Agent Router validates those sources and reconciles only an exact predecessor;
similar or ambiguous native content remains a conflict.

```python
current = Hook.from_path("./current/reviewer.json")
predecessor = Hook.from_path("./legacy/reviewer.json")

inspection = router.inspect_hook(current, predecessors=(predecessor,))
result = router.install_hook(current, predecessors=(predecessor,))
print(inspection.hook_transition, result.hook_transition)
```

`hook_transition` independently reports `legacy-replaced`, `legacy-pruned`,
`owned-restored`, or `owned-removed` when applicable. `converted` continues to
mean only an authorized cross-agent source conversion.

## CLI

```console
agent-router skill inspect ./reviewer --agent codex
agent-router skill install ./reviewer --agent codex
agent-router skill update ./reviewer --agent codex --scope project \
  --project-root ./repository
agent-router skill update ./reviewer --agent codex --scope project \
  --project-root ./repository --ignore-policy pattern \
  --ignore-pattern '/.agents/skills/*/'
agent-router skill update ./reviewer --agent codex --scope project \
  --project-root ./repository --ignore-policy none
agent-router skill uninstall reviewer --agent codex

agent-router hook inspect ./reviewer.json --agent claude
agent-router hook install ./reviewer.json --agent claude
agent-router hook install ./current/reviewer.json --agent claude \
  --predecessor ./legacy/reviewer.json
agent-router hook uninstall reviewer --agent claude
```

Shared options:

```text
--scope user|project
--project-root PATH
--destination PATH
--json
```

Install and hook-inspection commands also expose `--allow-conversion`.
Conversion is off by default and is limited to the portable command-hook subset
shared by Claude Code and Codex. Skills are never converted.

Hook inspect and install also accept repeatable `--predecessor PATH` options.
Skill commands and hook uninstall do not accept predecessor input.

`skill update` also accepts `--ignore-policy exact|pattern|none`; pattern mode
requires exactly one `--ignore-pattern`. The command defaults to user scope so
an update must explicitly select project scope and provide `--project-root`.

`--destination` replaces the resolved physical destination while retaining the
selected semantic scope. Project scope still requires `--project-root`. This is
useful for automation and isolated BDD tests without changing production safety
or ownership behavior.

## Native support

| Agent | Skills | Hooks or equivalent |
|---|---|---|
| Codex | user and project | user and project |
| Claude Code | user and project | user and project |
| Kimi Code CLI | user and project | user only |
| Pi | user and project | user and project extensions |

The Codex user skill root is `~/.codex/skills`. Default uninstall removes only an
intact projection previously installed by `agent-router`; unmanaged or modified
content fails closed. Explicit Python `force=True` is the narrow proven-owned
exception described above.

## Router state

Persistent ownership, plugin receipt, and artifact-policy metadata is kept out
of every native agent discovery and configuration surface. User-scoped state is
stored beneath `~/.z-agent-router`; project-scoped state is stored beneath the
selected repository's `.z-agent-router`. A destination override changes only the
native projection and does not move the semantically scoped metadata.

Valid legacy `.agent-router` records remain readable without mutation. The next
authorized lifecycle mutation writes or consumes current `.z-agent-router`
state and removes only the proven legacy record and empty legacy directories.
Malformed or divergent duplicate evidence fails closed.

## Development

Behave features and step bindings are owned by capability roots under `features/`.
Run affected BDD targets with `zpp behave bdd`, the complete audit with
`zpp behave bdd-audit --all`, and unit tests with `uv run pytest`.
