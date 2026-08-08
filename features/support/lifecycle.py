from __future__ import annotations

import json
from pathlib import Path

from agent_router import Agent, AgentRouter


def write_skill(
    root: Path, name: str = "reviewer", *, body: str = "Body", extra: str = ""
) -> Path:
    source = root / f"source-{name}"
    source.mkdir(parents=True, exist_ok=True)
    (source / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Reviews code\n{extra}---\n{body}\n",
        encoding="utf-8",
    )
    return source


def write_json_hook(
    root: Path,
    name: str = "reviewer",
    *,
    event: str = "PreToolUse",
    handler_type: str = "command",
    extra_handler: str = "",
) -> Path:
    handler: dict[str, object] = {"type": handler_type}
    if handler_type == "command":
        handler["command"] = "check"
    else:
        handler["prompt"] = "check"
    if extra_handler:
        handler[extra_handler] = True
    source = root / f"{name}.json"
    source.write_text(
        json.dumps({"hooks": {event: [{"matcher": "shell", "hooks": [handler]}]}}),
        encoding="utf-8",
    )
    return source


def write_kimi_hook(root: Path, name: str = "reviewer") -> Path:
    source = root / f"{name}.toml"
    source.write_text(
        '[[hooks]]\nevent = "PreToolUse"\nmatcher = "shell"\ncommand = "check"\n',
        encoding="utf-8",
    )
    return source


def write_pi_hook(root: Path, name: str = "reviewer") -> Path:
    source = root / f"{name}.ts"
    source.write_text("export default function extension() {}\n", encoding="utf-8")
    return source


def router(context, agent: Agent = Agent.CODEX) -> AgentRouter:
    return AgentRouter(agent, home=context.home)


def capture(context, action) -> None:
    try:
        context.result = action()
    except Exception as error:  # noqa: BLE001 - scenarios assert captured failures
        context.error = error
