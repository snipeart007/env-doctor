"""
Report incompatibility command for env-doctor CLI.

Executes scripts/notebooks and reports incompatibilities to Watsonx Orchestrate.
"""

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

from env_doctor.reporting.executor import (
    execute_script,
    execute_notebook,
    create_error_report,
    parse_error_traceback
)

console = Console()


def report_incompatibility(
    script: str = typer.Argument(..., help="Path to Python script or Jupyter notebook"),
    timeout: int = typer.Option(300, "--timeout", help="Execution timeout in seconds"),
    submit: bool = typer.Option(True, "--submit/--no-submit", help="Submit to Watsonx Orchestrate"),
    save_report: Optional[str] = typer.Option(None, "--save", help="Save Markdown report to file"),
    mock: bool = typer.Option(False, "--mock", help="Use mock mode for testing"),
) -> None:
    """
    Execute script and report incompatibilities to Watsonx Orchestrate.
    
    Runs a Python script or Jupyter notebook in a controlled environment,
    captures any errors cell-by-cell for notebooks, and optionally submits 
    a Markdown report to Watsonx Orchestrate for AI analysis.
    
    Examples:
        env-doctor report-incompatibility test.py
        env-doctor report-incompatibility notebook.ipynb --timeout 600
        env-doctor report-incompatibility script.py --no-submit
        env-doctor report-incompatibility test.py --save report.md
    """
    try:
        # Validate file exists
        script_path = Path(script)
        if not script_path.exists():
            console.print(f"[bold red]Error:[/bold red] File not found: {script}")
            raise typer.Exit(code=1)
        
        console.print(f"[bold blue]Executing:[/bold blue] {script}")
        console.print(f"[dim]Timeout: {timeout}s[/dim]")
        console.print()
        
        # Determine file type and execute
        is_notebook = script_path.suffix == '.ipynb'
        
        with console.status("[bold green]Running script...[/bold green]"):
            if is_notebook:
                result = execute_notebook(script, timeout=timeout)
            else:
                result = execute_script(script, timeout=timeout)
        
        # Display execution results
        console.print()
        
        if result['success']:
            console.print(
                Panel(
                    f"[green]✓ Script executed successfully![/green]\n\n"
                    f"Duration: {result['duration']:.2f}s",
                    title="Success",
                    border_style="green"
                )
            )
            
            # For scripts, we might still want to show output
            if not is_notebook and result.get('stdout'):
                console.print()
                console.print("[bold]Output:[/bold]")
                console.print(result['stdout'][:500])
                if len(result['stdout']) > 500:
                    console.print("[dim]... (truncated)[/dim]")
            
            raise typer.Exit(code=0)
        
        # Script failed - analyze error
        console.print(
            Panel(
                f"[red]✗ Script execution failed[/red]\n\n"
                f"Duration: {result['duration']:.2f}s",
                title="Execution Failed",
                border_style="red"
            )
        )
        console.print()
        
        # Display error information
        if result.get('error'):
            console.print(f"[bold red]Error:[/bold red] {result['error']}")
            console.print()
        
        # Display traceback if available (scripts)
        if not is_notebook and result.get('traceback'):
            console.print("[bold]Traceback:[/bold]")
            syntax = Syntax(
                result['traceback'],
                "python",
                theme="monokai",
                line_numbers=False
            )
            console.print(Panel(syntax, border_style="red"))
            console.print()
        
        # Create comprehensive error report (now contains Markdown)
        report = create_error_report(
            script_path=script,
            execution_result=result,
            include_environment=True
        )
        
        # Save report if requested
        if save_report:
            with open(save_report, 'w', encoding='utf-8') as f:
                f.write(report['markdown'])
            console.print(f"[green]✓ Markdown report saved to {save_report}[/green]")
            console.print()
        
        # Submit to Watsonx Orchestrate if requested
        if submit:
            try:
                _submit_to_watsonx(report['markdown'], mock=mock)
            except Exception as e:
                console.print()
                console.print(
                    Panel(
                        f"[yellow]⚠ Submission failed[/yellow]\n\n"
                        f"Error: {e}\n\n"
                        f"Report generated locally. You can retry submission later.",
                        title="Submission Error",
                        border_style="yellow"
                    )
                )
        else:
            console.print("[dim]Skipping submission (--no-submit)[/dim]")
        
        console.print()
        
        # Exit with error code
        raise typer.Exit(code=1)
        
    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print("\n[yellow]Execution cancelled by user[/yellow]")
        raise typer.Exit(code=130)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(code=1)


def _submit_to_watsonx(
    markdown_content: str,
    mock: bool = False
) -> None:
    """
    Submit Markdown report to Watsonx Orchestrate.
    
    Args:
        markdown_content: The formatted Markdown report
        mock: Use mock mode for testing
    """
    console.print("[bold blue]Submitting report to Watsonx Orchestrate...[/bold blue]")
    
    if mock:
        console.print("[dim]Mock mode: Submission skipped, but Markdown was generated successfully.[/dim]")
        # We could save it to a temp file in mock mode to simulate "sending"
        return

    # TODO: Implement Watsonx Orchestrate endpoint call
    # This will involve:
    # 1. Loading WATSONX_ORCHESTRATE_URL and API keys from environment
    # 2. Constructing the request payload with the markdown_content
    # 3. Handling the async/sync response from Orchestrate
    
    console.print("[yellow]Note: Watsonx Orchestrate integration is currently a placeholder.[/yellow]")
    console.print("[dim]Markdown payload size: {} bytes[/dim]".format(len(markdown_content)))
