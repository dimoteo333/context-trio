"""Typer CLI application for the Triad Orchestration System.

Commands:
    trio status              — Show current phase, task queue, recent logs
    trio plan <request>      — Generate Architect prompt
    trio implement [--task-id] — Generate Implementer prompt
    trio review [--task-id]  — Generate Auditor prompt
    trio add-task <json>     — Add a TaskPacket to the queue
    trio transition <phase>  — Manual phase transition
    trio init                — Initialize project structure (Python alternative to install.sh)
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .context import ContextManager
from .exceptions import ContextNotFoundError, TrioError
from .prompts import build_prompt
from .schemas import AgentRole, Phase, TaskPacket
from .state_machine import get_active_agent, get_valid_targets

app = typer.Typer(
    name="trio",
    help="Triad Orchestration System — multi-agent AI collaboration CLI.",
    no_args_is_help=True,
)
console = Console()


def _get_ctx_manager() -> ContextManager:
    """Return a ContextManager for the default path."""
    return ContextManager()


# ---------------------------------------------------------------------------
# trio status
# ---------------------------------------------------------------------------

@app.command()
def status() -> None:
    """Show current project phase, task queue, and recent activity."""
    mgr = _get_ctx_manager()
    try:
        ctx = mgr.load()
    except ContextNotFoundError:
        console.print(
            "[red]docs/CONTEXT.json not found.[/red] "
            "Run [bold]trio init[/bold] to initialize."
        )
        raise typer.Exit(1)

    # Phase panel
    active_agent = get_active_agent(ctx.global_phase)
    valid_targets = get_valid_targets(ctx.global_phase)
    agent_str = active_agent.value if active_agent else "—"
    targets_str = ", ".join(t.value for t in valid_targets) or "—"

    console.print(Panel(
        f"[bold]Phase:[/bold] {ctx.global_phase.value}\n"
        f"[bold]Active Agent:[/bold] {agent_str}\n"
        f"[bold]Valid Transitions:[/bold] {targets_str}\n"
        f"[bold]Current Task:[/bold] {ctx.current_task or '—'}\n"
        f"[bold]Last Updated:[/bold] {ctx.last_updated_by.value} "
        f"@ {ctx.last_updated_at}",
        title=f"[bold cyan]{ctx.project_name}[/bold cyan]",
    ))

    # Task queue table
    if ctx.task_queue:
        table = Table(title="Task Queue")
        table.add_column("ID", style="bold")
        table.add_column("Title")
        table.add_column("Priority")
        table.add_column("Depends On")
        for task in ctx.task_queue:
            table.add_row(
                task.task_id,
                task.title,
                task.priority.value,
                ", ".join(task.depends_on) or "—",
            )
        console.print(table)
    else:
        console.print("[dim]No tasks in queue.[/dim]")

    # Completed tasks
    if ctx.completed_tasks:
        console.print(
            f"\n[green]Completed:[/green] {', '.join(ctx.completed_tasks)}"
        )

    # Recent logs
    if ctx.reasoning_logs:
        console.print("\n[bold]Recent Activity:[/bold]")
        for log in ctx.reasoning_logs[-5:]:
            console.print(
                f"  [{log.agent.value}] {log.action}: {log.summary}"
            )

    # Known issues
    if ctx.known_issues:
        console.print(f"\n[yellow]Known Issues:[/yellow] {len(ctx.known_issues)}")


# ---------------------------------------------------------------------------
# trio plan
# ---------------------------------------------------------------------------

@app.command()
def plan(
    request: Annotated[str, typer.Argument(help="User request to plan")],
) -> None:
    """Generate an Architect system prompt for the given request."""
    mgr = _get_ctx_manager()
    try:
        ctx = mgr.load()
    except ContextNotFoundError:
        console.print("[red]docs/CONTEXT.json not found.[/red] Run [bold]trio init[/bold] first.")
        raise typer.Exit(1)

    prompt = build_prompt(
        AgentRole.ARCHITECT,
        ctx,
        user_request=request,
    )
    console.print(Panel(prompt, title="[bold magenta]Architect Prompt[/bold magenta]"))


# ---------------------------------------------------------------------------
# trio implement
# ---------------------------------------------------------------------------

@app.command()
def implement(
    task_id: Annotated[
        Optional[str],
        typer.Option("--task-id", "-t", help="Task ID to implement"),
    ] = None,
) -> None:
    """Generate an Implementer system prompt for a task."""
    mgr = _get_ctx_manager()
    try:
        ctx = mgr.load()
    except ContextNotFoundError:
        console.print("[red]docs/CONTEXT.json not found.[/red]")
        raise typer.Exit(1)

    task = _find_task(ctx.task_queue, task_id)
    if task is None:
        if task_id:
            console.print(f"[red]Task {task_id!r} not found in queue.[/red]")
        else:
            console.print("[red]No tasks in queue.[/red]")
        raise typer.Exit(1)

    prompt = build_prompt(AgentRole.IMPLEMENTER, ctx, task=task)
    console.print(Panel(prompt, title="[bold green]Implementer Prompt[/bold green]"))


# ---------------------------------------------------------------------------
# trio review
# ---------------------------------------------------------------------------

@app.command()
def review(
    task_id: Annotated[
        Optional[str],
        typer.Option("--task-id", "-t", help="Task ID to review"),
    ] = None,
) -> None:
    """Generate an Auditor system prompt for reviewing a task."""
    mgr = _get_ctx_manager()
    try:
        ctx = mgr.load()
    except ContextNotFoundError:
        console.print("[red]docs/CONTEXT.json not found.[/red]")
        raise typer.Exit(1)

    task = _find_task(ctx.task_queue, task_id)
    if task is None:
        if task_id:
            console.print(f"[red]Task {task_id!r} not found in queue.[/red]")
        else:
            console.print("[red]No tasks in queue.[/red]")
        raise typer.Exit(1)

    prompt = build_prompt(AgentRole.AUDITOR, ctx, task=task)
    console.print(Panel(prompt, title="[bold yellow]Auditor Prompt[/bold yellow]"))


# ---------------------------------------------------------------------------
# trio add-task
# ---------------------------------------------------------------------------

@app.command("add-task")
def add_task(
    task_json: Annotated[str, typer.Argument(help="Task Packet as JSON string")],
) -> None:
    """Add a TaskPacket to the task queue."""
    mgr = _get_ctx_manager()
    try:
        ctx = mgr.load()
    except ContextNotFoundError:
        console.print("[red]docs/CONTEXT.json not found.[/red]")
        raise typer.Exit(1)

    try:
        data = json.loads(task_json)
        task = TaskPacket.model_validate(data)
    except (json.JSONDecodeError, Exception) as exc:
        console.print(f"[red]Invalid task JSON:[/red] {exc}")
        raise typer.Exit(1)

    mgr.add_task(task, AgentRole.ARCHITECT)
    console.print(f"[green]Added task {task.task_id}: {task.title}[/green]")


# ---------------------------------------------------------------------------
# trio transition
# ---------------------------------------------------------------------------

@app.command()
def transition(
    phase: Annotated[str, typer.Argument(help="Target phase")],
    agent: Annotated[
        str,
        typer.Option("--agent", "-a", help="Agent performing transition"),
    ] = "architect",
) -> None:
    """Manually transition to a new workflow phase."""
    mgr = _get_ctx_manager()
    try:
        ctx = mgr.load()
    except ContextNotFoundError:
        console.print("[red]docs/CONTEXT.json not found.[/red]")
        raise typer.Exit(1)

    try:
        target = Phase(phase)
    except ValueError:
        valid = ", ".join(p.value for p in Phase)
        console.print(f"[red]Invalid phase '{phase}'.[/red] Valid: {valid}")
        raise typer.Exit(1)

    try:
        agent_role = AgentRole(agent)
    except ValueError:
        valid = ", ".join(a.value for a in AgentRole)
        console.print(f"[red]Invalid agent '{agent}'.[/red] Valid: {valid}")
        raise typer.Exit(1)

    try:
        mgr.update_phase(target, agent_role)
    except TrioError as exc:
        console.print(f"[red]Transition failed:[/red] {exc}")
        raise typer.Exit(1)

    console.print(
        f"[green]Phase transitioned:[/green] "
        f"{ctx.global_phase.value} -> {target.value}"
    )


# ---------------------------------------------------------------------------
# trio init
# ---------------------------------------------------------------------------

@app.command()
def init(
    project_name: Annotated[
        Optional[str],
        typer.Option("--name", "-n", help="Project name (auto-detected if omitted)"),
    ] = None,
) -> None:
    """Initialize context-trio project structure (Python alternative to install.sh)."""
    cwd = Path.cwd()
    name = project_name or cwd.name

    # Create directories
    for d in ["docs", "docs/logs", "src", "tests"]:
        (cwd / d).mkdir(parents=True, exist_ok=True)

    # Initialize CONTEXT.json (idempotent)
    context_path = cwd / "docs" / "CONTEXT.json"
    if not context_path.exists():
        ContextManager.init_context(context_path, name)
        console.print("[green]Created docs/CONTEXT.json[/green]")
    else:
        console.print("[dim]docs/CONTEXT.json already exists, skipping.[/dim]")

    # Create doc templates (idempotent)
    _templates: dict[str, str] = {
        "docs/PRD.md": f"# Product Requirements Document — {name}\n\n> TODO: Define requirements.\n",
        "docs/ARCHITECTURE.md": f"# Architecture — {name}\n\n> TODO: Define system architecture.\n",
        "docs/DECISIONS.md": f"# Architecture Decision Records — {name}\n\n> TODO: Record decisions.\n",
        "docs/CHANGELOG.md": f"# Changelog — {name}\n\nAll notable changes to this project.\n",
    }

    for rel_path, content in _templates.items():
        full_path = cwd / rel_path
        if not full_path.exists():
            full_path.write_text(content, encoding="utf-8")
            console.print(f"[green]Created {rel_path}[/green]")
        else:
            console.print(f"[dim]{rel_path} already exists, skipping.[/dim]")

    # Copy CLAUDE.md and AGENTS.md from context-trio package if not present
    trio_root = Path(__file__).resolve().parent.parent.parent
    for filename in ["CLAUDE.md", "AGENTS.md"]:
        source = trio_root / filename
        dest = cwd / filename
        if not dest.exists() and source.exists():
            shutil.copy2(source, dest)
            console.print(f"[green]Copied {filename}[/green]")
        elif dest.exists():
            console.print(f"[dim]{filename} already exists, skipping.[/dim]")

    console.print(f"\n[bold green]Project '{name}' initialized![/bold green]")


# ---------------------------------------------------------------------------
# Version callback
# ---------------------------------------------------------------------------

def _version_callback(value: bool) -> None:
    if value:
        console.print(f"context-trio v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-v", callback=_version_callback, is_eager=True),
    ] = None,
) -> None:
    """Triad Orchestration System — multi-agent AI collaboration CLI."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_task(
    queue: list[TaskPacket],
    task_id: str | None,
) -> TaskPacket | None:
    """Find a task in the queue by ID, or return the first one."""
    if not queue:
        return None
    if task_id:
        for t in queue:
            if t.task_id == task_id:
                return t
        return None
    return queue[0]
