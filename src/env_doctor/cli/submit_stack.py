"""
Submit stack command for env-doctor CLI.

Submits a verified stable stack to the GitHub repository via Cloudflare Worker.
"""

import os
from typing import List, Optional

import httpx
import typer
from rich.console import Console
from rich.panel import Panel

from env_doctor.database.repository import RepositoryManager
from env_doctor.scanner.environment import (
    get_cuda_version,
    get_installed_packages,
    get_python_version,
)
from env_doctor.utils.config import load_config

console = Console()


def submit_stack(
    name: str = typer.Argument(..., help="Name of the stable stack (e.g., 'torch-2.4-transformers-4.44')"),
    description: str = typer.Option(..., "--desc", help="Description of the stack and its use case"),
    confidence: str = typer.Option("stable", "--confidence", help="Confidence level (production-tested, stable, experimental)"),
    cuda_version: Optional[str] = typer.Option(None, "--cuda", help="Target CUDA version"),
    env_system: Optional[str] = typer.Option(None, "--platform", help="Target platform (linux, win32)"),
    python_version: Optional[str] = typer.Option(None, "--python", help="Python version requirement"),
    use_current: bool = typer.Option(True, "--current/--no-current", help="Include all currently installed packages"),
    packages: Optional[List[str]] = typer.Option(None, "--package", help="Specific packages to include (name==version)"),
) -> None:
    """
    Submit a verified stable stack to the community database.
    
    Captures your current environment (or specific packages) and submits it
    as a 'known-good' configuration to the GitHub repository via the secure proxy.
    
    Examples:
        env-doctor submit-stack my-stack --desc "Optimized for Llama-3 fine-tuning"
        env-doctor submit-stack prod-vllm --cuda 12.1 --platform linux --package vllm==0.5.1
    """
    try:
        console.print("[bold blue]🚀 Preparing stable stack submission...[/bold blue]")
        
        # 1. Gather environment info if not provided
        if cuda_version is None:
            cuda_version = get_cuda_version()
        
        if python_version is None:
            full_py = get_python_version()
            python_version = ".".join(full_py.split(".")[:2]) # Use major.minor
            
        if env_system is None:
            import sys
            env_system = sys.platform

        # 2. Build package list
        stack_packages = []
        
        if use_current:
            installed = get_installed_packages()
            for pkg in installed:
                stack_packages.append({
                    "name": pkg["name"],
                    "version": pkg["version"]
                })
        
        if packages:
            for pkg_spec in packages:
                if "==" in pkg_spec:
                    p_name, p_ver = pkg_spec.split("==", 1)
                    # Check if already added (overwrite if manual provided)
                    stack_packages = [p for p in stack_packages if p["name"].lower() != p_name.lower()]
                    stack_packages.append({"name": p_name, "version": p_ver})
                else:
                    console.print(f"[yellow]Warning: Skipping invalid package spec '{pkg_spec}'. Use 'name==version'.[/yellow]")

        if not stack_packages:
            console.print("[bold red]Error:[/bold red] No packages identified for the stack.")
            raise typer.Exit(code=1)

        # 3. Construct Stack Object
        stack_obj = {
            "name": name,
            "cuda_version": cuda_version,
            "env_system": env_system,
            "python_version": python_version,
            "confidence": confidence,
            "description": description,
            "packages": stack_packages
        }

        # 4. Discover Worker URL
        config = load_config()
        proxy_url = os.getenv("ENV_DOCTOR_PROXY_URL") or config.worker_url
        
        if not proxy_url:
            repo_manager = RepositoryManager(config)
            proxy_url = repo_manager.get_worker_url()

        if not proxy_url:
            console.print(
                Panel(
                    "[yellow]⚠ Secure Proxy URL not configured.[/yellow]\n\n"
                    "Submission requires an authorized endpoint. Please set\n"
                    "[bold]ENV_DOCTOR_PROXY_URL[/bold] or ensure [bold]worker.txt[/bold] exists in the repo.",
                    title="Configuration Missing",
                    border_style="yellow"
                )
            )
            raise typer.Exit(code=1)

        # 5. Submit to Worker
        submission_url = f"{proxy_url.rstrip('/')}/stable-stack"
        console.print(f"[dim]Submitting to: {submission_url}[/dim]")
        
        with httpx.Client() as client:
            response = client.post(
                submission_url,
                json=stack_obj,
                timeout=30.0
            )
            
            if response.status_code == 200:
                console.print(f"[bold green]✓ Success![/bold green] Stack '{name}' has been registered.")
                console.print("[dim]It will be available to all users after their next 'update-db' run.[/dim]")
            else:
                console.print(f"[bold red]✗ Submission failed:[/bold red] {response.status_code}")
                console.print(f"[dim]{response.text}[/dim]")
                raise typer.Exit(code=1)

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)
