from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Annotated, Callable

import typer

from agent_router import (
    Agent,
    AgentEnvironment,
    AgentRouter,
    AgentRouterError,
    ArtifactManifest,
    ArtifactPolicy,
    PluginArtifactContext,
    PluginRef,
)

plugin_app = typer.Typer(no_args_is_help=True)
artifact_app = typer.Typer(no_args_is_help=True)
plugin_app.add_typer(artifact_app, name="artifact")

AgentOption = Annotated[list[Agent], typer.Option("--agent")]
DestinationOption = Annotated[Path | None, typer.Option("--destination")]
JsonOption = Annotated[bool, typer.Option("--json")]
ScopeOption = Annotated[str, typer.Option("--scope")]
SourceOption = Annotated[str | None, typer.Option("--source")]


@dataclass(frozen=True, slots=True)
class _EmptyArtifactExtension:
    manifest: ArtifactManifest

    def locate(self, context: PluginArtifactContext) -> tuple[PurePath, ...]:
        del context
        return ()


def _one_agent(agents: list[Agent]) -> Agent:
    if len(agents) != 1:
        raise typer.BadParameter(
            "exactly one --agent is required", param_hint="--agent"
        )
    return agents[0]


def _router(
    agents: list[Agent], destination: Path | None, artifact_id: str | None = None
) -> AgentRouter:
    environment = AgentEnvironment(destination) if destination is not None else None
    extensions = (
        (_EmptyArtifactExtension(ArtifactManifest(artifact_id, "1")),)
        if artifact_id is not None
        else ()
    )
    return AgentRouter(
        _one_agent(agents), environment=environment, extensions=extensions
    )


def _ref(agent: Agent, native_ref: str, scope: str, source: str | None) -> PluginRef:
    return PluginRef(agent, native_ref, scope, source)


def _run(action: Callable[[], object], json_output: bool) -> None:
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
    if isinstance(result, tuple):
        value = [item.to_dict() for item in result]
        text = f"{len(result)} plugin record(s)"
    else:
        value = result.to_dict()  # type: ignore[attr-defined]
        text = f"{value.get('operation', 'artifact')}: {value.get('status', value.get('effective'))}"
    if json_output:
        typer.echo(json.dumps({"result": value}, sort_keys=True))
    else:
        typer.echo(text)


@plugin_app.command("discover")
def discover_plugins(
    agent: AgentOption,
    available: Annotated[bool, typer.Option("--available")] = False,
    destination: DestinationOption = None,
    json_output: JsonOption = False,
) -> None:
    _run(
        lambda: _router(agent, destination).discover_plugins(
            include_available=available
        ),
        json_output,
    )


@plugin_app.command("install")
def install_plugin(
    native_ref: str,
    agent: AgentOption,
    scope: ScopeOption = "user",
    source: SourceOption = None,
    trust: Annotated[bool, typer.Option("--trust")] = False,
    destination: DestinationOption = None,
    json_output: JsonOption = False,
) -> None:
    selected = _one_agent(agent)
    _run(
        lambda: _router(agent, destination).install_plugin(
            _ref(selected, native_ref, scope, source), trust=trust
        ),
        json_output,
    )


@plugin_app.command("update")
def update_plugin(
    native_ref: str,
    agent: AgentOption,
    scope: ScopeOption = "user",
    source: SourceOption = None,
    destination: DestinationOption = None,
    json_output: JsonOption = False,
) -> None:
    selected = _one_agent(agent)
    _run(
        lambda: _router(agent, destination).update_plugin(
            _ref(selected, native_ref, scope, source)
        ),
        json_output,
    )


@plugin_app.command("remove")
def remove_plugin(
    native_ref: str,
    agent: AgentOption,
    scope: ScopeOption = "user",
    source: SourceOption = None,
    destination: DestinationOption = None,
    json_output: JsonOption = False,
) -> None:
    selected = _one_agent(agent)
    _run(
        lambda: _router(agent, destination).remove_plugin(
            _ref(selected, native_ref, scope, source)
        ),
        json_output,
    )


@artifact_app.command("status")
def artifact_status(
    native_ref: str,
    artifact_id: str,
    agent: AgentOption,
    scope: ScopeOption = "user",
    source: SourceOption = None,
    destination: DestinationOption = None,
    json_output: JsonOption = False,
) -> None:
    selected = _one_agent(agent)
    _run(
        lambda: _router(agent, destination, artifact_id).artifact_status(
            _ref(selected, native_ref, scope, source), artifact_id
        ),
        json_output,
    )


@artifact_app.command("set")
def set_artifact_policy_command(
    native_ref: str,
    artifact_id: str,
    policy: ArtifactPolicy,
    agent: AgentOption,
    scope: ScopeOption = "user",
    source: SourceOption = None,
    destination: DestinationOption = None,
    json_output: JsonOption = False,
) -> None:
    selected = _one_agent(agent)
    _run(
        lambda: _router(agent, destination, artifact_id).set_artifact_policy(
            _ref(selected, native_ref, scope, source), artifact_id, policy
        ),
        json_output,
    )
