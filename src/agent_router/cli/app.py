from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from agent_router import (
    Agent,
    AgentRouter,
    AgentRouterError,
    Hook,
    GitIgnorePolicy,
    IgnoreMode,
    LifecycleResult,
    Scope,
    Skill,
)
from agent_router.cli.plugins import plugin_app

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
skill_app = typer.Typer(no_args_is_help=True)
hook_app = typer.Typer(no_args_is_help=True)
app.add_typer(skill_app, name="skill")
app.add_typer(hook_app, name="hook")
app.add_typer(plugin_app, name="plugin")

AgentOption = Annotated[list[Agent], typer.Option("--agent")]
ScopeOption = Annotated[Scope, typer.Option("--scope")]
ProjectOption = Annotated[Path | None, typer.Option("--project-root")]
DestinationOption = Annotated[Path | None, typer.Option("--destination")]
JsonOption = Annotated[bool, typer.Option("--json")]
ConversionOption = Annotated[bool, typer.Option("--allow-conversion")]
PredecessorOption = Annotated[list[Path] | None, typer.Option("--predecessor")]
IgnorePolicyOption = Annotated[IgnoreMode, typer.Option("--ignore-policy")]
IgnorePatternOption = Annotated[list[str] | None, typer.Option("--ignore-pattern")]


def _run(action: Callable[[], LifecycleResult], json_output: bool) -> None:
    try:
        result = action()
    except AgentRouterError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(error.exit_status) from error
    except typer.BadParameter:
        raise
    except Exception as error:
        typer.echo(f"unexpected operational failure: {error}", err=True)
        raise typer.Exit(1) from error
    if json_output:
        typer.echo(json.dumps({"result": result.to_dict()}, sort_keys=True))
    else:
        typer.echo(
            f"{result.kind.value} {result.name}: {result.status} "
            f"for {result.agent.value} at {result.destination}"
        )


def _one_agent(agents: list[Agent]) -> Agent:
    if len(agents) != 1:
        raise typer.BadParameter(
            "exactly one --agent is required", param_hint="--agent"
        )
    return agents[0]


def _hook_predecessors(paths: list[Path] | None) -> tuple[Hook, ...]:
    return tuple(Hook.from_path(path) for path in paths or ())


@skill_app.command("inspect")
def inspect_skill(
    source: Path,
    agent: AgentOption,
    scope: ScopeOption = Scope.USER,
    project_root: ProjectOption = None,
    destination: DestinationOption = None,
    json_output: JsonOption = False,
) -> None:
    _run(
        lambda: AgentRouter(_one_agent(agent)).inspect_skill(
            Skill.from_path(source),
            scope=scope,
            project_root=project_root,
            destination=destination,
        ),
        json_output,
    )


@skill_app.command("install")
def install_skill(
    source: Path,
    agent: AgentOption,
    scope: ScopeOption = Scope.USER,
    project_root: ProjectOption = None,
    destination: DestinationOption = None,
    allow_conversion: ConversionOption = False,
    json_output: JsonOption = False,
) -> None:
    _run(
        lambda: AgentRouter(_one_agent(agent)).install_skill(
            Skill.from_path(source),
            scope=scope,
            project_root=project_root,
            destination=destination,
            allow_conversion=allow_conversion,
        ),
        json_output,
    )


@skill_app.command("update")
def update_skill(
    source: Path,
    agent: AgentOption,
    scope: ScopeOption = Scope.USER,
    project_root: ProjectOption = None,
    destination: DestinationOption = None,
    ignore_policy: IgnorePolicyOption = IgnoreMode.EXACT,
    ignore_pattern: IgnorePatternOption = None,
    json_output: JsonOption = False,
) -> None:
    patterns = ignore_pattern or []
    try:
        if len(patterns) > 1:
            raise ValueError("pattern ignore policy requires one pattern")
        policy = GitIgnorePolicy(
            ignore_policy,
            patterns[0] if patterns else None,
        )
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="--ignore-pattern") from error
    _run(
        lambda: AgentRouter(_one_agent(agent)).update_skill(
            Skill.from_path(source),
            scope=scope,
            project_root=project_root,
            destination=destination,
            ignore_policy=policy,
        ),
        json_output,
    )


@skill_app.command("uninstall")
def uninstall_skill(
    name: str,
    agent: AgentOption,
    scope: ScopeOption = Scope.USER,
    project_root: ProjectOption = None,
    destination: DestinationOption = None,
    json_output: JsonOption = False,
) -> None:
    _run(
        lambda: AgentRouter(_one_agent(agent)).uninstall_skill(
            name,
            scope=scope,
            project_root=project_root,
            destination=destination,
        ),
        json_output,
    )


@hook_app.command("inspect")
def inspect_hook(
    source: Path,
    agent: AgentOption,
    scope: ScopeOption = Scope.USER,
    project_root: ProjectOption = None,
    destination: DestinationOption = None,
    allow_conversion: ConversionOption = False,
    predecessor: PredecessorOption = None,
    json_output: JsonOption = False,
) -> None:
    _run(
        lambda: AgentRouter(_one_agent(agent)).inspect_hook(
            Hook.from_path(source),
            scope=scope,
            project_root=project_root,
            destination=destination,
            allow_conversion=allow_conversion,
            predecessors=_hook_predecessors(predecessor),
        ),
        json_output,
    )


@hook_app.command("install")
def install_hook(
    source: Path,
    agent: AgentOption,
    scope: ScopeOption = Scope.USER,
    project_root: ProjectOption = None,
    destination: DestinationOption = None,
    allow_conversion: ConversionOption = False,
    predecessor: PredecessorOption = None,
    json_output: JsonOption = False,
) -> None:
    _run(
        lambda: AgentRouter(_one_agent(agent)).install_hook(
            Hook.from_path(source),
            scope=scope,
            project_root=project_root,
            destination=destination,
            allow_conversion=allow_conversion,
            predecessors=_hook_predecessors(predecessor),
        ),
        json_output,
    )


@hook_app.command("uninstall")
def uninstall_hook(
    name: str,
    agent: AgentOption,
    scope: ScopeOption = Scope.USER,
    project_root: ProjectOption = None,
    destination: DestinationOption = None,
    json_output: JsonOption = False,
) -> None:
    _run(
        lambda: AgentRouter(_one_agent(agent)).uninstall_hook(
            name,
            scope=scope,
            project_root=project_root,
            destination=destination,
        ),
        json_output,
    )
