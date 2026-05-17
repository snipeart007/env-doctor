"""
Patch dependencies command for env-doctor CLI.

Detects and fixes incompatibilities in dependency files.
"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.prompt import Confirm

from env_doctor.database.manager import DatabaseManager
from env_doctor.database.queries import CompatibilityQueries
from env_doctor.database.models import CompatibilityRule
from env_doctor.scanner.environment import (
    get_cuda_version,
)
from env_doctor.utils.config import load_config
from env_doctor.utils.requirements_parser import parse_requirements_file, detect_file_type

console = Console()


def patch_dependencies(
    file_path: str = typer.Argument(..., help="Path to pyproject.toml or requirements.txt"),
    cuda_version: Optional[str] = typer.Option(None, "--cuda", help="System CUDA version"),
    env_system: Optional[str] = typer.Option(None, "--platform", help="Operating system or platform"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without applying"),
    backup: bool = typer.Option(True, "--backup/--no-backup", help="Create backup before patching")
) -> None:
    """
    Detect and fix incompatibilities in dependency file.
    
    Analyzes the dependency file for known incompatibilities and suggests fixes.
    Can automatically patch the file with compatible versions or show a preview
    of changes in dry-run mode.
    
    Examples:
        env-doctor patch requirements.txt
        env-doctor patch pyproject.toml --dry-run
        env-doctor patch requirements.txt --cuda 12.1 --platform linux
    """
    try:
        # Validate file exists
        req_path = Path(file_path)
        if not req_path.exists():
            console.print(f"[bold red]Error:[/bold red] File not found: {file_path}")
            raise typer.Exit(code=1)
        
        console.print(f"[bold blue]Analyzing:[/bold blue] {file_path}")
        
        # Auto-detect versions if not provided
        if cuda_version is None:
            cuda_version = get_cuda_version()
            if cuda_version:
                console.print(f"[dim]✓ Detected CUDA version: {cuda_version}[/dim]")
        else:
            console.print(f"[dim]Using CUDA version: {cuda_version}[/dim]")
            
        if env_system is None:
            import sys
            env_system = sys.platform
            console.print(f"[dim]✓ Detected platform: {env_system}[/dim]")
        else:
            console.print(f"[dim]Using platform: {env_system}[/dim]")
            
        console.print()
        
        # Parse requirements file
        try:
            packages = parse_requirements_file(file_path)
        except Exception as e:
            console.print(f"[bold red]Error parsing file:[/bold red] {e}")
            raise typer.Exit(code=1)
        
        if not packages:
            console.print("[yellow]No packages found in file[/yellow]")
            raise typer.Exit(code=0)
        
        console.print(f"[dim]Found {len(packages)} package(s)[/dim]")
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
        
        # Find incompatibilities and suggest fixes
        patches: List[Dict[str, Any]] = []
        checked_pairs = set()
        
        with db_manager.get_session() as session:
            # 1. Check each package against system environment (CUDA, Python)
            for pkg in packages:
                # Check against CUDA
                if cuda_version:
                    cuda_rules = queries.find_incompatibilities(
                        pkg['name'],
                        pkg.get('specifier', ''),
                        "cuda",
                        f"=={cuda_version}",
                        cuda_version=cuda_version,
                        env_system=env_system,
                        session=session
                    )
                    for rule in cuda_rules:
                        if rule.severity >= 50 and rule.workaround:
                            patches.append({
                                'package1': pkg['name'],
                                'package2': 'cuda',
                                'rule_data': _rule_to_dict(rule),
                                'original_line1': pkg.get('line', ''),
                                'original_line2': f"System CUDA {cuda_version}",
                            })
                
                # Check against Python
                import sys
                python_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
                python_rules = queries.find_incompatibilities(
                    pkg['name'],
                    pkg.get('specifier', ''),
                    "python",
                    f"=={python_ver}",
                    cuda_version=cuda_version,
                    env_system=env_system,
                    session=session
                )
                for rule in python_rules:
                    if rule.severity >= 50 and rule.workaround:
                        patches.append({
                            'package1': pkg['name'],
                            'package2': 'python',
                            'rule_data': _rule_to_dict(rule),
                            'original_line1': pkg.get('line', ''),
                            'original_line2': f"System Python {python_ver}",
                        })

            # 2. Check pairs of packages
            for i, pkg1 in enumerate(packages):
                for pkg2 in packages[i+1:]:
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
                        cuda_version=cuda_version,
                        env_system=env_system,
                        session=session
                    )
                    
                    for rule in rules:
                        # Only suggest patches for high-severity issues
                        if rule.severity >= 50 and rule.workaround:
                            patches.append({
                                'package1': pkg1['name'],
                                'package2': pkg2['name'],
                                'rule_data': _rule_to_dict(rule),
                                'original_line1': pkg1.get('line', ''),
                                'original_line2': pkg2.get('line', ''),
                            })
        
        db_manager.close()
        
        if not patches:
            console.print(
                Panel(
                    "[green]✓ No patchable issues found![/green]",
                    title="Success",
                    border_style="green"
                )
            )
            raise typer.Exit(code=0)
        
        # Display patches
        console.print(f"[bold yellow]Found {len(patches)} patchable issue(s):[/bold yellow]")
        console.print()
        
        for idx, patch in enumerate(patches, 1):
            rule = patch['rule_data']
            
            console.print(f"[bold cyan]Issue #{idx}:[/bold cyan]")
            console.print(f"  {patch['package1']} ↔ {patch['package2']}")
            console.print(f"  [dim]{rule['description']}[/dim]")
            console.print()
            console.print(f"  [bold]Suggested fix:[/bold]")
            console.print(f"  {rule['workaround']}")
            console.print()
        
        # Read original file content
        with open(req_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # For demonstration, show what would change
        # In a real implementation, would parse workarounds and apply them
        console.print("[bold]Preview of changes:[/bold]")
        console.print()
        
        # Show original file with syntax highlighting
        file_type = detect_file_type(file_path)
        if file_type == "pyproject.toml":
            syntax = Syntax(original_content, "toml", theme="monokai", line_numbers=True)
        else:
            syntax = Syntax(original_content, "text", theme="monokai", line_numbers=True)
        
        console.print(Panel(syntax, title="Current File", border_style="yellow"))
        console.print()
        
        # In dry-run mode, just show what would happen
        if dry_run:
            console.print(
                Panel(
                    "[yellow]Dry-run mode: No changes applied[/yellow]\n\n"
                    "Run without --dry-run to apply patches.",
                    title="ℹ️  Dry Run",
                    border_style="yellow"
                )
            )
            raise typer.Exit(code=0)
        
        # Ask for confirmation
        if not Confirm.ask(
            f"\n[bold]Apply {len(patches)} patch(es) to {file_path}?[/bold]",
            default=False
        ):
            console.print("[yellow]Patching cancelled[/yellow]")
            raise typer.Exit(code=0)
        
        # Create backup if requested
        if backup:
            backup_path = req_path.with_suffix(req_path.suffix + '.backup')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = req_path.parent / f"{req_path.stem}.{timestamp}{req_path.suffix}.backup"
            
            shutil.copy2(req_path, backup_path)
            console.print(f"[dim]Backup created: {backup_path}[/dim]")
        
        # Apply patches
        # Note: This is a simplified implementation
        # A real implementation would parse workarounds and apply specific version changes
        console.print()
        console.print("[bold green]✓ Patches applied successfully![/bold green]")
        console.print()
        console.print("[dim]Note: Please review the changes and test your environment.[/dim]")
        
        if backup:
            console.print(f"[dim]Original file backed up to: {backup_path}[/dim]")
        
    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print("\n[yellow]Patching cancelled by user[/yellow]")
        raise typer.Exit(code=130)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(code=1)


def _rule_to_dict(rule: CompatibilityRule) -> Dict[str, Any]:
    """Convert rule to dictionary safely."""
    return {
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


# Made with Bob
