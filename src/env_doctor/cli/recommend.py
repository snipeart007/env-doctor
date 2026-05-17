"""
Recommend stack command for env-doctor CLI.

Recommends stable package stacks based on environment and requirements.
"""

from pathlib import Path
from typing import Dict, List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm, Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn

from env_doctor.core.recommendations import (
    RecommendationEngine,
    MigrationPathGenerator,
    ScoredStack,
)
from env_doctor.database.manager import DatabaseManager
from env_doctor.database.queries import StackQueries
from env_doctor.scanner.environment import (
    get_python_version,
    get_cuda_version,
    get_installed_packages,
)
from env_doctor.utils.config import load_config

console = Console()


def recommend_stack(
    cuda_version: Optional[str] = typer.Option(None, "--cuda", help="CUDA version (e.g., 12.1)"),
    python_version: Optional[str] = typer.Option(None, "--python", help="Python version (e.g., 3.10)"),
    platform: Optional[str] = typer.Option(None, "--platform", help="Target platform/OS (e.g., linux, win32)"),
    packages: Optional[List[str]] = typer.Option(None, "--package", help="Required packages"),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", help="Interactive selection"),
    show_migration: bool = typer.Option(True, "--migration/--no-migration", help="Show migration paths"),
    min_score: float = typer.Option(0.0, "--min-score", help="Minimum recommendation score (0-100)"),
    confidence: Optional[str] = typer.Option(None, "--confidence", help="Minimum confidence level")
) -> None:
    """
    Recommend stable package stack for your environment.
    
    Analyzes your system configuration and recommends tested, stable package
    combinations from the env-doctor database. Uses a 4-factor scoring system:
    - Confidence (40%): production-tested > stable > community-tested > experimental
    - Package overlap (30%): How many required packages are in the stack
    - Recency (20%): Newer stacks preferred
    - Community adoption (10%): Based on confidence and usage
    
    Examples:
        env-doctor recommend
        env-doctor recommend --cuda 12.1 --platform linux
        env-doctor recommend --package torch --package transformers
        env-doctor recommend --min-score 50 --confidence stable
        env-doctor recommend --no-interactive --no-migration
    """
    try:
        console.print("[bold blue]🔍 Analyzing environment and finding recommendations...[/bold blue]")
        console.print()
        
        # Auto-detect versions if not provided
        if cuda_version is None:
            cuda_version = get_cuda_version()
            if cuda_version:
                console.print(f"[dim]✓ Detected CUDA version: {cuda_version}[/dim]")
            else:
                console.print("[dim]✓ No CUDA detected (CPU-only stacks will be recommended)[/dim]")
        else:
            console.print(f"[dim]Using CUDA version: {cuda_version}[/dim]")
        
        if python_version is None:
            python_version = get_python_version()
            # Extract major.minor version
            parts = python_version.split('.')
            if len(parts) >= 2:
                python_version = f"{parts[0]}.{parts[1]}"
            console.print(f"[dim]✓ Detected Python version: {python_version}[/dim]")
        else:
            console.print(f"[dim]Using Python version: {python_version}[/dim]")

        if platform is None:
            import sys
            platform = sys.platform
            console.print(f"[dim]✓ Detected platform: {platform}[/dim]")
        else:
            console.print(f"[dim]Using platform: {platform}[/dim]")
        current_packages_list = get_installed_packages()
        current_packages = {pkg["name"]: pkg["version"] for pkg in current_packages_list}
        console.print(f"[dim]✓ Found {len(current_packages)} installed packages[/dim]")
        console.print()
        
        # Load configuration and database
        config = load_config()
        db_path = str(config.get_expanded_db_path())
        
        if not Path(db_path).exists():
            console.print(
                Panel(
                    "[yellow]Database not found. Run 'env-doctor update-db' first.[/yellow]",
                    title="⚠️  Warning",
                    border_style="yellow"
                )
            )
            raise typer.Exit(code=1)
        
        db_manager = DatabaseManager(db_path)
        queries = StackQueries(db_manager)
        
        # All DB processing inside one session block
        with db_manager.get_session() as session:
            # Query for matching stacks
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Searching database...", total=None)
                
                stacks = queries.find_matching_stacks(
                    cuda_version=cuda_version,
                    python_version=python_version,
                    required_packages=packages,
                    platform=platform,
                    confidence_threshold=confidence,
                    session=session
                )
                
                progress.update(task, completed=True)
            
            if not stacks:
                console.print(
                    Panel(
                        "[yellow]No matching stacks found for your environment.[/yellow]\n\n"
                        f"CUDA: {cuda_version or 'any'}\n"
                        f"Python: {python_version or 'any'}\n"
                        f"Required packages: {', '.join(packages) if packages else 'none'}\n"
                        f"Confidence: {confidence or 'any'}",
                        title="⚠️  No Results",
                        border_style="yellow"
                    )
                )
                db_manager.close()
                raise typer.Exit(code=0)
            
            # Get stacks with packages
            stacks_with_packages = []
            for stack in stacks:
                stack_packages = queries.get_stack_packages(stack.uid, session=session)
                stacks_with_packages.append((stack, stack_packages))
            
            # Score and rank stacks
            console.print("[bold blue]📊 Scoring and ranking stacks...[/bold blue]")
            console.print()
            
            engine = RecommendationEngine()
            
            # Build required packages dict
            required_packages_dict = {}
            if packages:
                for pkg in packages:
                    if "==" in pkg:
                        name, version = pkg.split("==", 1)
                        required_packages_dict[name] = f"=={version}"
                    else:
                        required_packages_dict[pkg] = ""
            
            scored_stacks = engine.rank_stacks(
                stacks_with_packages,
                required_packages=required_packages_dict,
                current_packages=current_packages,
                python_version=python_version,
                cuda_version=cuda_version,
                min_score=min_score
            )
            
            if not scored_stacks:
                console.print(
                    Panel(
                        f"[yellow]No stacks found with score >= {min_score}[/yellow]\n\n"
                        "Try lowering the --min-score threshold or adjusting your requirements.",
                        title="⚠️  No Results",
                        border_style="yellow"
                    )
                )
                db_manager.close()
                raise typer.Exit(code=0)
            
            # Display recommendations
            console.print(f"[bold green]✨ Found {len(scored_stacks)} recommended stack(s):[/bold green]")
            console.print()
            
            migration_generator = MigrationPathGenerator()
            
            displayed_count = 0
            for idx, scored_stack in enumerate(scored_stacks, 1):
                _display_stack_recommendation(
                    idx, scored_stack, current_packages,
                    show_migration, migration_generator, interactive,
                    idx < len(scored_stacks)
                )
                displayed_count = idx
                
                if interactive and idx < len(scored_stacks):
                    if not Confirm.ask("Show next recommendation?", default=True):
                        break
                
                if idx < len(scored_stacks):
                    console.print("─" * console.width)
                    console.print()
        
        db_manager.close()
        
        # Summary
        console.print(
            Panel(
                f"[green]✓ Displayed {displayed_count} of {len(scored_stacks)} recommended stack(s)[/green]",
                border_style="green"
            )
        )
        
    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print("\n[yellow]Recommendation cancelled by user[/yellow]")
        raise typer.Exit(code=130)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(code=1)


def _display_stack_recommendation(
    idx: int,
    scored_stack: ScoredStack,
    current_packages: Dict[str, str],
    show_migration: bool,
    migration_generator: MigrationPathGenerator,
    interactive: bool,
    has_more: bool
) -> None:
    """Display a single stack recommendation with details."""
    stack = scored_stack.stack
    
    # Create stack info panel
    info = f"[bold]{stack.name}[/bold]\n\n"
    info += f"{stack.description}\n\n"
    
    # Environment details
    info += f"[cyan]CUDA:[/cyan] {stack.cuda_version or 'CPU-only'}\n"
    info += f"[cyan]Python:[/cyan] {stack.python_version}\n"
    info += f"[cyan]Confidence:[/cyan] {stack.confidence_level}\n"
    info += f"[cyan]Packages:[/cyan] {len(scored_stack.packages)}\n\n"
    
    # Score breakdown
    info += f"[bold yellow]Score: {scored_stack.total_score:.1f}/100[/bold yellow]\n"
    info += f"[dim]{scored_stack.explanation}[/dim]"
    
    console.print(
        Panel(
            info,
            title=f"📦 Stack #{idx} (Rank {idx})",
            border_style="green" if scored_stack.total_score >= 70 else "yellow"
        )
    )
    
    # Display "Why Recommended" section
    _display_why_recommended(scored_stack)
    
    # Display packages table
    _display_packages_table(scored_stack, current_packages)
    
    # Show migration path if requested
    if show_migration and current_packages:
        _display_migration_path(scored_stack, current_packages, migration_generator)
    
    # Show installation command
    console.print("\n[bold]Installation command:[/bold]")
    install_cmd = "pip install " + " ".join(
        f"{pkg.package_name}=={pkg.version}" for pkg in scored_stack.packages
    )
    console.print(f"[dim]{install_cmd}[/dim]")
    console.print()


def _display_why_recommended(scored_stack: ScoredStack) -> None:
    """Display why this stack is recommended."""
    console.print("\n[bold cyan]Why Recommended:[/bold cyan]")
    
    reasons = []
    
    # Confidence
    if scored_stack.confidence_score >= 30:
        reasons.append(f"✓ High confidence level ({scored_stack.stack.confidence_level})")
    elif scored_stack.confidence_score >= 20:
        reasons.append(f"• Good confidence level ({scored_stack.stack.confidence_level})")
    
    # Package overlap
    if scored_stack.matching_packages:
        match_pct = scored_stack.get_match_percentage()
        if match_pct == 100:
            reasons.append(f"✓ All required packages included ({len(scored_stack.matching_packages)} packages)")
        elif match_pct >= 80:
            reasons.append(f"• Most required packages included ({len(scored_stack.matching_packages)}/{len(scored_stack.matching_packages) + len(scored_stack.missing_packages)})")
    
    # Recency
    age_days = (datetime.utcnow() - scored_stack.stack.created_at).days
    if age_days <= 30:
        reasons.append(f"✓ Very recent stack ({age_days} days old)")
    elif age_days <= 90:
        reasons.append(f"• Recent stack ({age_days} days old)")
    
    # Missing packages warning
    if scored_stack.missing_packages:
        reasons.append(f"⚠ Missing {len(scored_stack.missing_packages)} required package(s): {', '.join(sorted(scored_stack.missing_packages))}")
    
    for reason in reasons:
        console.print(f"  {reason}")


def _display_packages_table(scored_stack: ScoredStack, current_packages: Dict[str, str]) -> None:
    """Display packages in a table with comparison to current environment."""
    console.print("\n[bold cyan]Packages:[/bold cyan]")
    
    pkg_table = Table(show_header=True, header_style="bold cyan", box=None)
    pkg_table.add_column("Package", style="cyan")
    pkg_table.add_column("Version", style="green")
    pkg_table.add_column("Current", style="dim")
    pkg_table.add_column("Status", style="yellow")
    
    for pkg in sorted(scored_stack.packages, key=lambda p: p.package_name):
        current_version = current_packages.get(pkg.package_name, "")
        
        if not current_version:
            status = "➕ New"
            status_style = "green"
        elif current_version == pkg.version:
            status = "✓ Same"
            status_style = "dim"
        else:
            try:
                from packaging.version import Version
                if Version(pkg.version) > Version(current_version):
                    status = "⬆ Upgrade"
                    status_style = "blue"
                else:
                    status = "⬇ Downgrade"
                    status_style = "yellow"
            except Exception:
                status = "↔ Change"
                status_style = "yellow"
        
        pkg_table.add_row(
            pkg.package_name,
            pkg.version,
            current_version or "-",
            f"[{status_style}]{status}[/{status_style}]"
        )
    
    console.print(pkg_table)


def _display_migration_path(
    scored_stack: ScoredStack,
    current_packages: Dict[str, str],
    migration_generator: MigrationPathGenerator
) -> None:
    """Display migration path from current environment to target stack."""
    console.print("\n[bold cyan]Migration Path:[/bold cyan]")
    
    migration_plan = migration_generator.generate_migration_plan(
        current_packages, scored_stack
    )
    
    if not migration_plan.steps:
        console.print("  [dim]No changes needed - environment already matches stack[/dim]")
        return
    
    # Display summary
    risk_color = {"low": "green", "medium": "yellow", "high": "red"}[migration_plan.risk_level]
    console.print(f"  [bold]Summary:[/bold] {migration_plan.get_summary()}")
    console.print(f"  [bold]Risk Level:[/bold] [{risk_color}]{migration_plan.risk_level}[/{risk_color}]")
    console.print(f"  [bold]Estimated Time:[/bold] ~{migration_plan.estimated_time} minutes")
    
    # Display warnings
    if migration_plan.warnings:
        console.print(f"\n  [bold yellow]⚠ Warnings:[/bold yellow]")
        for warning in migration_plan.warnings:
            console.print(f"    • {warning}")
    
    # Display steps
    console.print(f"\n  [bold]Steps:[/bold]")
    for i, step in enumerate(migration_plan.steps[:10], 1):  # Show first 10 steps
        icon = {"install": "➕", "upgrade": "⬆", "downgrade": "⬇", "remove": "➖"}[step.action]
        console.print(f"    {i}. {icon} {step}")
    
    if len(migration_plan.steps) > 10:
        console.print(f"    [dim]... and {len(migration_plan.steps) - 10} more steps[/dim]")


# Import datetime for age calculation
from datetime import datetime


# Made with Bob