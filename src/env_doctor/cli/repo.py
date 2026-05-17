"""
Repository management command for env-doctor CLI.

Allows users to configure and manage database intelligence repositories.
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from env_doctor.utils.config import load_config, save_config

console = Console()
app = typer.Typer(help="Manage intelligence repositories")


@app.command(name="set")
def set_repo(
    source: str = typer.Argument(..., help="Git URL, local path, or GitHub owner/repo"),
    branch: str = typer.Option("main", "--branch", "-b", help="Git branch to use")
) -> None:
    """
    Set the active intelligence repository source.
    
    Examples:
        env-doctor repo set snipeart007/env-doctor-db
        env-doctor repo set https://github.com/my-org/custom-rules.git --branch dev
        env-doctor repo set C:/Users/name/projects/my-local-rules
    """
    config = load_config()
    config.repo_source = source
    config.github_branch = branch
    save_config(config)
    
    console.print(
        Panel(
            f"[green]Repository source updated![/green]\n\n"
            f"[bold]Source:[/bold] {source}\n"
            f"[bold]Branch:[/bold] {branch}\n\n"
            "Run [bold]env-doctor update-db[/bold] to apply changes.",
            title="✓ Success",
            border_style="green"
        )
    )


@app.command(name="set-worker")
def set_worker(url: str = typer.Argument(..., help="Cloudflare Worker URL")) -> None:
    """
    Manually set the secure proxy worker URL.
    
    Note: This will be overwritten by 'update-db' if a worker.txt 
    file is found in the repository.
    """
    config = load_config()
    config.worker_url = url
    save_config(config)
    
    console.print(
        Panel(
            f"Worker URL updated to: [bold cyan]{url}[/bold cyan]\n\n"
            "[dim]Note: This may be overwritten by 'update-db' if the repo contains a worker.txt.[/dim]",
            title="✓ Success",
            border_style="green"
        )
    )


@app.command(name="show")
def show_repo() -> None:
    """Show current repository configuration."""
    config = load_config()
    
    table = Table(title="Repository Configuration", show_header=False)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Source", config.repo_source)
    table.add_row("Branch", config.github_branch)
    table.add_row("Worker URL", config.worker_url or "Not set")
    table.add_row("Cache Dir", str(config.get_expanded_repo_cache_dir()))
    
    console.print(table)


# Made with Bob
