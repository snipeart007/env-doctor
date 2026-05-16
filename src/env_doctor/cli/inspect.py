"""
Inspect environment command for env-doctor CLI.

Scans and displays current environment information including Python version,
CUDA, GPU, and installed packages.
"""

import json
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from env_doctor.scanner.environment import (
    get_python_version,
    get_cuda_version,
    get_gpu_info,
    get_platform_info,
    get_installed_packages,
    get_full_environment_info
)

console = Console()


def inspect_env(
    output_format: str = typer.Option("table", "--format", help="Output format: table, json"),
    save: Optional[str] = typer.Option(None, "--save", help="Save to file"),
    packages: bool = typer.Option(True, "--packages/--no-packages", help="Include package list")
) -> None:
    """
    Scan and display current environment information.
    
    Detects Python version, CUDA version, GPU information, and installed packages.
    Results can be displayed as a formatted table or JSON, and optionally saved to a file.
    
    Examples:
        env-doctor inspect
        env-doctor inspect --format json
        env-doctor inspect --save environment.json
        env-doctor inspect --no-packages
    """
    try:
        console.print("[bold blue]Scanning environment...[/bold blue]")
        
        # Get environment information
        python_version = get_python_version()
        cuda_version = get_cuda_version()
        gpu_info = get_gpu_info()
        platform_info = get_platform_info()
        
        if output_format == "json":
            # JSON output
            env_data = {
                "python_version": python_version,
                "cuda_version": cuda_version,
                "gpu_info": gpu_info,
                "platform": platform_info
            }
            
            if packages:
                env_data["packages"] = get_installed_packages()
            
            json_output = json.dumps(env_data, indent=2)
            
            if save:
                # Save to file
                with open(save, 'w', encoding='utf-8') as f:
                    f.write(json_output)
                console.print(f"[green]Environment info saved to {save}[/green]")
            else:
                # Print to console
                console.print(json_output)
        
        else:
            # Table output
            console.print()
            
            # System Information Panel
            system_table = Table(show_header=False, box=None, padding=(0, 2))
            system_table.add_column("Property", style="cyan")
            system_table.add_column("Value", style="white")
            
            system_table.add_row("Python Version", f"[bold]{python_version}[/bold]")
            system_table.add_row("Platform", f"{platform_info['system']} {platform_info['release']}")
            system_table.add_row("Architecture", platform_info['machine'])
            
            console.print(Panel(system_table, title="🐍 System Information", border_style="blue"))
            
            # CUDA & GPU Information Panel
            if cuda_version or gpu_info:
                gpu_table = Table(show_header=False, box=None, padding=(0, 2))
                gpu_table.add_column("Property", style="cyan")
                gpu_table.add_column("Value", style="white")
                
                if cuda_version:
                    gpu_table.add_row("CUDA Version", f"[bold green]{cuda_version}[/bold green]")
                else:
                    gpu_table.add_row("CUDA Version", "[dim]Not detected[/dim]")
                
                if gpu_info:
                    gpu_table.add_row("GPU Count", str(gpu_info['count']))
                    for idx, gpu in enumerate(gpu_info['gpus']):
                        gpu_table.add_row(f"GPU {idx}", gpu['name'])
                        gpu_table.add_row(f"  Memory", gpu['memory_total'])
                        if 'driver_version' in gpu:
                            gpu_table.add_row(f"  Driver", gpu['driver_version'])
                else:
                    gpu_table.add_row("GPU", "[dim]Not detected[/dim]")
                
                console.print(Panel(gpu_table, title="🎮 CUDA & GPU", border_style="green"))
            else:
                console.print(
                    Panel(
                        "[dim]No CUDA or GPU detected[/dim]",
                        title="🎮 CUDA & GPU",
                        border_style="yellow"
                    )
                )
            
            # Installed Packages
            if packages:
                console.print()
                console.print("[bold blue]Fetching installed packages...[/bold blue]")
                
                installed_packages = get_installed_packages()
                
                if installed_packages:
                    # Create packages table
                    pkg_table = Table(
                        title=f"📦 Installed Packages ({len(installed_packages)} total)",
                        show_header=True,
                        header_style="bold cyan"
                    )
                    pkg_table.add_column("Package", style="cyan")
                    pkg_table.add_column("Version", style="green")
                    
                    # Show first 20 packages, or all if less than 20
                    display_count = min(20, len(installed_packages))
                    for pkg in installed_packages[:display_count]:
                        pkg_table.add_row(pkg['name'], pkg['version'])
                    
                    if len(installed_packages) > display_count:
                        pkg_table.add_row(
                            f"[dim]... and {len(installed_packages) - display_count} more[/dim]",
                            ""
                        )
                    
                    console.print(pkg_table)
                    console.print(
                        f"[dim]Tip: Use --format json to see all packages or --no-packages to skip[/dim]"
                    )
                else:
                    console.print("[yellow]No packages found[/yellow]")
            
            # Save option for table format
            if save:
                env_data = get_full_environment_info()
                with open(save, 'w', encoding='utf-8') as f:
                    json.dump(env_data, f, indent=2)
                console.print()
                console.print(f"[green]✓ Environment info saved to {save}[/green]")
        
        console.print()
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Inspection cancelled by user[/yellow]")
        raise typer.Exit(code=130)
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(code=1)


# Made with Bob