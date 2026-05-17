"""
Update database command for env-doctor CLI.

Fetches YAML files from a Git repository or local directory and compiles them into the local SQLite database.
"""

import sys
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.table import Table

from env_doctor.database.compiler import YAMLCompiler
from env_doctor.database.manager import DatabaseManager
from env_doctor.database.repository import RepositoryManager
from env_doctor.utils.config import load_config

console = Console()


def update_db(
    force: bool = typer.Option(False, "--force", help="Force update even if cache is fresh"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")
) -> None:
    """
    Update local database from repository.
    
    Fetches compatibility rules, stable stacks, and runtime profiles from the
    configured repository (Git URL or local path) and compiles them into the local SQLite database.
    
    Examples:
        env-doctor update-db
        env-doctor update-db --force
        env-doctor update-db --verbose
    """
    try:
        # Load configuration
        config = load_config()
        config.ensure_directories()
        
        if verbose:
            console.print(f"[dim]Database path: {config.get_expanded_db_path()}[/dim]")
            console.print(f"[dim]Repo source: {config.repo_source}[/dim]")
            console.print(f"[dim]Branch: {config.github_branch}[/dim]")
        
        # Initialize database manager
        db_path = str(config.get_expanded_db_path())
        db_manager = DatabaseManager(db_path)
        
        # Create tables if they don't exist
        console.print("[bold blue]Initializing database...[/bold blue]")
        db_manager.create_tables()
        
        # Initialize Repository Manager
        repo_manager = RepositoryManager(config)
        
        # Discover and update worker URL from repo
        worker_url = repo_manager.get_worker_url()
        if worker_url:
            from env_doctor.utils.config import save_config
            if config.worker_url != worker_url:
                config.worker_url = worker_url
                save_config(config)
                if verbose:
                    console.print(f"[dim]✓ Synchronized worker URL: {worker_url}[/dim]")
        
        # Initialize YAML compiler
        compiler = YAMLCompiler(db_manager, repo_manager=repo_manager)
        
        # Progress tracking
        stats = {"files_fetched": 0, "current_file": "", "current_step": 0, "total_steps": 0}
        
        def progress_callback(stage: str, current: int, total: int) -> None:
            """Callback for progress updates."""
            stats["current_file"] = stage
            stats["current_step"] = current
            stats["total_steps"] = total
        
        # Compile with progress bar
        console.print("[bold blue]Fetching and compiling YAML files...[/bold blue]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            
            # Create progress task
            task = progress.add_task("[cyan]Updating database...", total=100)
            
            try:
                # Run compilation
                compilation_stats = compiler.compile_all(
                    branch=config.github_branch,
                    progress_callback=progress_callback
                )
                
                progress.update(task, completed=100)
                
            except Exception as e:
                progress.stop()
                console.print(f"[bold red]Error during compilation:[/bold red] {e}")
                if verbose:
                    import traceback
                    console.print(f"[dim]{traceback.format_exc()}[/dim]")
                raise typer.Exit(code=1)
        
        # Display results
        console.print()
        
        if compilation_stats["errors"] > 0:
            console.print(
                Panel(
                    f"[yellow]Update completed with {compilation_stats['errors']} error(s)[/yellow]",
                    title="⚠️  Warning",
                    border_style="yellow"
                )
            )
        else:
            console.print(
                Panel(
                    "[green]Database updated successfully![/green]",
                    title="✓ Success",
                    border_style="green"
                )
            )
        
        # Create statistics table
        table = Table(title="Update Statistics", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right", style="green")
        
        table.add_row("YAML Files Read", str(compilation_stats["files_fetched"]))
        table.add_row("Compatibility Rules", str(compilation_stats["rules_processed"]))
        table.add_row("Stable Stacks", str(compilation_stats["stacks_processed"]))
        table.add_row("Runtime Profiles", str(compilation_stats["profiles_processed"]))
        
        if compilation_stats["errors"] > 0:
            table.add_row("Errors", str(compilation_stats["errors"]), style="red")
        
        console.print(table)
        console.print()
        
        # Close database connection
        db_manager.close()
        
        # Exit with appropriate code
        if compilation_stats["errors"] > 0:
            raise typer.Exit(code=1)
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Update cancelled by user[/yellow]")
        raise typer.Exit(code=130)
        
    except Exception as e:
        console.print(f"[bold red]Fatal error:[/bold red] {e}")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(code=1)


# Made with Bob
