"""`cognilance` CLI commands."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from cognilance.config import DEFAULT_REGISTRY_PORT, Config
from cognilance.core.agent import CognilanceAgent
from cognilance.registry.client import RegistryClient, RegistryError
from cognilance.registry.local import ensure_local_registry
from cognilance.registry.server import create_registry_app

app = typer.Typer(
    name="cognilance",
    help="The Marketplace of Minds — build, register, and hire AI agents.",
    no_args_is_help=True,
)
console = Console()


def _load_agent_from_file(path: Path) -> CognilanceAgent:
    spec = importlib.util.spec_from_file_location("cognilance_agent_module", path)
    if spec is None or spec.loader is None:
        raise typer.BadParameter(f"Cannot load agent from {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["cognilance_agent_module"] = module
    spec.loader.exec_module(module)

    for attr in dir(module):
        obj = getattr(module, attr)
        if isinstance(obj, CognilanceAgent):
            return obj

    raise typer.BadParameter(
        f"No CognilanceAgent instance found in {path}. "
        "Define `agent = CognilanceAgent(...)` in the file."
    )


@app.command()
def registry(
    port: Annotated[
        int, typer.Option("--port", "-p", help="Port for the local registry")
    ] = DEFAULT_REGISTRY_PORT,
    host: Annotated[str, typer.Option("--host", help="Host to bind to")] = "127.0.0.1",
) -> None:
    """Start the local Cognilance registry (for development)."""
    console.print(
        f"[bold green]Registry[/bold green] listening on [cyan]http://{host}:{port}[/cyan]"
    )
    uvicorn.run(create_registry_app(), host=host, port=port)


@app.command()
def run(
    agent_file: Annotated[Path, typer.Argument(help="Path to the agent Python file")],
    port: Annotated[int, typer.Option("--port", "-p", help="Port to run the agent on")] = 8000,
    host: Annotated[str, typer.Option("--host", help="Host to bind to")] = "0.0.0.0",
    no_register: Annotated[
        bool, typer.Option("--no-register", help="Skip registry registration")
    ] = False,
) -> None:
    """Run an agent locally."""
    if not agent_file.exists():
        raise typer.BadParameter(f"File not found: {agent_file}")

    agent = _load_agent_from_file(agent_file)
    agent.host = host
    agent._port = port
    agent._config = Config.from_env(port=port)

    if not no_register:
        ensure_local_registry(agent._config.registry_url)

    console.print(f"[bold green]Running[/bold green] {agent.name} on port {port}")
    agent.run(register=not no_register)


@app.command()
def register(
    agent_file: Annotated[Path, typer.Argument(help="Path to the agent Python file")],
    url: Annotated[str, typer.Option("--url", help="Public URL of the externally-hosted agent")],
) -> None:
    """Register an externally-hosted agent with the Cognilance registry."""
    if not agent_file.exists():
        raise typer.BadParameter(f"File not found: {agent_file}")

    agent = _load_agent_from_file(agent_file)

    async def _register() -> None:
        card = await agent.register_external(url)
        console.print(f"[bold green]Registered[/bold green] {card.name} as [cyan]{card.id}[/cyan]")
        console.print(f"URL: {card.url}")

    asyncio.run(_register())


@app.command()
def discover(
    skills: Annotated[
        list[str] | None,
        typer.Option("--skill", "-s", help="Filter by skill (repeatable)"),
    ] = None,
    tags: Annotated[
        list[str] | None,
        typer.Option("--tag", "-t", help="Filter by tag (repeatable)"),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 10,
) -> None:
    """Discover agents on the Cognilance platform."""
    config = Config.from_env()

    async def _discover() -> None:
        registry = RegistryClient(
            registry_url=config.registry_url,
            api_key=config.require_api_key(),
        )
        try:
            agents = await registry.discover(skills=skills, tags=tags, limit=limit)
        except RegistryError as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            raise typer.Exit(1) from exc
        finally:
            await registry.close()

        if not agents:
            console.print("[yellow]No agents found.[/yellow]")
            return

        table = Table(title="Discovered Agents")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="bold")
        table.add_column("Skills")
        table.add_column("URL")
        table.add_column("Online")

        for a in agents:
            skill_names = ", ".join(s.name for s in a.skills)
            table.add_row(
                a.id or "—",
                a.name,
                skill_names,
                a.url,
                "✓" if a.online else "✗",
            )

        console.print(table)

    asyncio.run(_discover())


@app.command()
def info(
    agent_id: Annotated[str, typer.Argument(help="Agent ID to look up")],
) -> None:
    """Get info about a specific agent."""
    config = Config.from_env()

    async def _info() -> None:
        registry = RegistryClient(
            registry_url=config.registry_url,
            api_key=config.require_api_key(),
        )
        try:
            agent = await registry.get_agent(agent_id)
        except RegistryError as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            raise typer.Exit(1) from exc
        finally:
            await registry.close()

        console.print(f"[bold]{agent.name}[/bold] ({agent.id})")
        console.print(f"Description: {agent.description or '—'}")
        console.print(f"URL: {agent.url}")
        console.print(f"Visibility: {agent.visibility.value}")
        console.print(f"Online: {'yes' if agent.online else 'no'}")
        if agent.skills:
            console.print("Skills:")
            for s in agent.skills:
                tags = f" [{', '.join(s.tags)}]" if s.tags else ""
                console.print(f"  • {s.name}{tags}")

    asyncio.run(_info())


if __name__ == "__main__":
    app()
