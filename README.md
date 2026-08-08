# agent-router

`agent-router` installs, inspects, reconciles, and uninstalls Agent Skills and
native hooks for Codex, Claude Code, Kimi Code CLI, and Pi.

It is an importable library first. The Typer CLI is optional.

## Install

```console
uv add agent-router
uv add "agent-router[cli]"
```

Run the CLI without installing it into a project:

```console
uvx --from "agent-router[cli]" agent-router --help
```

## Python

```python
from agent_router import Agent, AgentRouter, Skill

router = AgentRouter(Agent.CODEX)
skill = Skill.from_path("./reviewer")

result = router.install_skill(skill)
print(result.status, result.destination)

router.uninstall_skill(skill.name)
```

Every router is bound to one agent. Operations use user scope by default;
project scope requires an explicit project root.

```python
from agent_router import Scope

router.install_skill(
    skill,
    scope=Scope.PROJECT,
    project_root="./repository",
)
```

## CLI

```console
agent-router skill inspect ./reviewer --agent codex
agent-router skill install ./reviewer --agent codex
agent-router skill uninstall reviewer --agent codex

agent-router hook inspect ./reviewer.json --agent claude
agent-router hook install ./reviewer.json --agent claude
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

The Codex user skill root is `~/.codex/skills`. Uninstall removes only an intact
projection previously installed by `agent-router`; unmanaged or modified content
fails closed.
