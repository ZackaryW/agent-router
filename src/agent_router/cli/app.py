from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Callable

import typer

from agent_router import Agent, AgentRouter, AgentRouterError, Hook, LifecycleResult, Scope, Skill


app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
skill_app = typer.Typer(no_args_is_help=True)
hook_app = typer.Typer(no_args_is_help=True)
app.add_typer(skill_app, name="skill")
app.add_typer(hook_app, name="hook")

AgentOption = Annotated[Agent, typer.Option("--agent")]
ScopeOption = Annotated[Scope, typer.Option("--scope")]
ProjectOption = Annotated[Path | None, typer.Option("--project-root")]
DestinationOption = Annotated[Path | None, typer.Option("--destination")]
JsonOption = Annotated[bool, typer.Option("--json")]
ConversionOption = Annotated[bool, typer.Option("--allow-conversion")]


def _run(action: Callable[[], LifecycleResult], json_output: bool) -> None:
    try:
        result = action()
    except AgentRouterError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(error.exit_status) from error
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
        lambda: AgentRouter(agent).inspect_skill(
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
        lambda: AgentRouter(agent).install_skill(
            Skill.from_path(source),
            scope=scope,
            project_root=project_root,
            destination=destination,
            allow_conversion=allow_conversion,
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
        lambda: AgentRouter(agent).uninstall_skill(
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
    json_output: JsonOption = False,
) -> None:
    _run(
        lambda: AgentRouter(agent).inspect_hook(
            Hook.from_path(source),
            scope=scope,
            project_root=project_root,
            destination=destination,
            allow_conversion=allow_conversion,
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
    json_output: JsonOption = False,
) -> None:
    _run(
        lambda: AgentRouter(agent).install_hook(
            Hook.from_path(source),
            scope=scope,
            project_root=project_root,
            destination=destination,
            allow_conversion=allow_conversion,
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
        lambda: AgentRouter(agent).uninstall_hook(
            name,
            scope=scope,
            project_root=project_root,
            destination=destination,
        ),
        json_output,
    )
