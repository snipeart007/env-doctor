"""
Check compatibility command for env-doctor CLI.

Checks compatibility of dependencies in requirements files against the database.
"""

from pathlib import Path
from typing import List, Dict, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from packaging.specifiers import SpecifierSet

from env_doctor.database.manager import DatabaseManager
from env_doctor.database.queries import CompatibilityQueries
from env_doctor.utils.config import load_config
from env_doctor.utils.requirements_parser import parse_requirements_file

console = Console()


def check_compatibility(
    requirements_file: str = typer.Argument(..., help="Path to requirements.txt or pyproject.toml"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")
) -> None:
    """
    Check compatibility of dependencies in requirements file.
    
    Analyzes the specified requirements file and checks for known incompatibilities
    between packages using the env-doctor database. Reports issues with severity
    levels and suggested workarounds.
    
    Examples:
        env-doctor check requirements.txt
        env-doctor check pyproject.toml --verbose
    """
    db_manager = None
    try:
        # Validate file exists
        req_path = Path(requirements_file)
        if not req_path.exists():
            console.print(f"[bold red]Error:[/bold red] File not found: {requirements_file}")
            raise typer.Exit(code=1)
        
        console.print(f"[bold blue]Checking compatibility for:[/bold blue] {requirements_file}")
        console.print()
        
        # Parse requirements file
        try:
            packages = parse_requirements_file(requirements_file)
        except Exception as e:
            console.print(f"[bold red]Error parsing file:[/bold red] {e}")
            raise typer.Exit(code=1)
        
        if not packages:
            console.print("[yellow]No packages found in requirements file[/yellow]")
            return
        
        console.print(f"[dim]Found {len(packages)} package(s) to check[/dim]")
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
        queries = CompatibilityQueries(db_manager)
        
        # Check each package for incompatibilities
        issues: List[Dict[str, Any]] = []
        checked_pairs = set()
        
        with db_manager.get_session() as session:
            for i, pkg1 in enumerate(packages):
                for pkg2 in packages[i+1:]:
                    # Create unique pair identifier
                    pair_key = tuple(sorted([pkg1['name'], pkg2['name']]))
                    if pair_key in checked_pairs:
                        continue
                    checked_pairs.add(pair_key)
                    
                    # Query for incompatibilities
                    rules = queries.find_incompatibilities(
                        pkg1['name'],
                        pkg1.get('specifier', ''),
                        pkg2['name'],
                        pkg2.get('specifier', ''),
                        session=session
                    )
                    
                    for rule in rules:
                        # Copy data to avoid detached instance errors
                        issues.append({
                            'package1': pkg1['name'],
                            'version1': pkg1.get('specifier', 'any'),
                            'package2': pkg2['name'],
                            'version2': pkg2.get('specifier', 'any'),
                            'rule_data': {
                                'uid': rule.uid,
                                'package_name': rule.package_name,
                                'package_version_range': rule.package_version_range,
                                'dependency_name': rule.dependency_name,
                                'dependency_version_range': rule.dependency_version_range,
                                'compatibility_type': rule.compatibility_type,
                                'confidence_level': rule.confidence_level,
                                'severity': rule.severity,
                                'description': rule.description,
                                'workaround': rule.workaround
                            }
                        })
        
        # Display results
        if not issues:
            console.print(
                Panel(
                    "[green]✓ No known compatibility issues found![/green]",
                    title="Success",
                    border_style="green"
                )
            )
            return
        
        # Categorize issues by severity
        critical_issues = [i for i in issues if i['rule_data']['severity'] >= 80]
        warnings = [i for i in issues if 50 <= i['rule_data']['severity'] < 80]
        info = [i for i in issues if i['rule_data']['severity'] < 50]
        
        # Display summary
        summary_table = Table(show_header=False, box=None)
        summary_table.add_column("Level", style="bold")
        summary_table.add_column("Count", justify="right")
        
        if critical_issues:
            summary_table.add_row("🔴 Critical", str(len(critical_issues)), style="red")
        if warnings:
            summary_table.add_row("🟡 Warnings", str(len(warnings)), style="yellow")
        if info:
            summary_table.add_row("🔵 Info", str(len(info)), style="blue")
        
        console.print(Panel(summary_table, title="⚠️  Compatibility Issues Found", border_style="red"))
        console.print()
        
        # Display critical issues
        if critical_issues:
            console.print("[bold red]🔴 Critical Issues:[/bold red]")
            for issue in critical_issues:
                _display_issue(issue, verbose)
            console.print()
        
        # Display warnings
        if warnings:
            console.print("[bold yellow]🟡 Warnings:[/bold yellow]")
            for issue in warnings:
                _display_issue(issue, verbose)
            console.print()
        
        # Display info (only in verbose mode)
        if info and verbose:
            console.print("[bold blue]🔵 Informational:[/bold blue]")
            for issue in info:
                _display_issue(issue, verbose)
            console.print()
        
        # Exit with appropriate code
        if critical_issues:
            raise typer.Exit(code=2)
        elif warnings:
            raise typer.Exit(code=1)
        
    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print("\n[yellow]Check cancelled by user[/yellow]")
        raise typer.Exit(code=130)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(code=1)
    finally:
        if db_manager:
            db_manager.close()


def _display_issue(issue: Dict[str, Any], verbose: bool) -> None:
    """Display a single compatibility issue."""
    rule = issue['rule_data']
    
    # Determine color based on severity
    severity = rule['severity']
    if severity >= 80:
        color = "red"
        icon = "🔴"
    elif severity >= 50:
        color = "yellow"
        icon = "🟡"
    else:
        color = "blue"
        icon = "🔵"
    
    # Create issue panel
    content = f"[bold]{issue['package1']}[/bold] {issue['version1']} ↔ [bold]{issue['package2']}[/bold] {issue['version2']}\n\n"
    content += f"{rule['description']}\n\n"
    content += f"[dim]Type: {rule['compatibility_type']}[/dim]\n"
    content += f"[dim]Confidence: {rule['confidence_level']}[/dim]\n"
    content += f"[dim]Severity: {severity}/100[/dim]"
    
    if rule.get('workaround'):
        content += f"\n\n[bold cyan]Workaround:[/bold cyan]\n{rule['workaround']}"
    
    if verbose:
        content += f"\n\n[dim]Rule UID: {rule['uid']}[/dim]"
    
    console.print(
        Panel(
            content,
            title=f"{icon} Incompatibility Detected",
            border_style=color
        )
    )


# Made with Bob
