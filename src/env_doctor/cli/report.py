"""
Report incompatibility command for env-doctor CLI.

Executes scripts/notebooks and reports incompatibilities to the database.
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
from env_doctor.reporting.submission_client import (
    SubmissionClient,
    SubmissionConfig,
    SubmissionStatus
)
from env_doctor.reporting.ai_analyzer import (
    AIAnalyzer,
    WatsonxConfig
)
from env_doctor.reporting.pr_creator import (
    PRCreator,
    GitHubConfig
)

console = Console()


def report_incompatibility(
    script: str = typer.Argument(..., help="Path to Python script or Jupyter notebook"),
    timeout: int = typer.Option(300, "--timeout", help="Execution timeout in seconds"),
    submit: bool = typer.Option(True, "--submit/--no-submit", help="Submit to serverless endpoint"),
    save_report: Optional[str] = typer.Option(None, "--save", help="Save report to file"),
    mock: bool = typer.Option(False, "--mock", help="Use mock mode for testing"),
    wait: bool = typer.Option(False, "--wait", help="Wait for AI analysis to complete"),
    create_pr: bool = typer.Option(False, "--create-pr", help="Create GitHub PR with analysis")
) -> None:
    """
    Execute script and report incompatibilities.
    
    Runs a Python script or Jupyter notebook in a controlled environment,
    captures any errors, and optionally submits the incompatibility report
    to the env-doctor serverless endpoint for AI analysis.
    
    Examples:
        env-doctor report-incompatibility test.py
        env-doctor report-incompatibility notebook.ipynb --timeout 600
        env-doctor report-incompatibility script.py --no-submit
        env-doctor report-incompatibility test.py --save report.json
        env-doctor report-incompatibility test.py --mock --wait
        env-doctor report-incompatibility test.py --wait --create-pr
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
            
            if result['stdout']:
                console.print()
                console.print("[bold]Output:[/bold]")
                console.print(result['stdout'][:500])  # Show first 500 chars
                if len(result['stdout']) > 500:
                    console.print("[dim]... (truncated)[/dim]")
            
            raise typer.Exit(code=0)
        
        # Script failed - analyze error
        console.print(
            Panel(
                f"[red]✗ Script execution failed[/red]\n\n"
                f"Exit code: {result['exit_code']}\n"
                f"Duration: {result['duration']:.2f}s",
                title="Execution Failed",
                border_style="red"
            )
        )
        console.print()
        
        # Display error information
        if result['error']:
            console.print(f"[bold red]Error:[/bold red] {result['error']}")
            console.print()
        
        # Display traceback with syntax highlighting
        if result['traceback']:
            console.print("[bold]Traceback:[/bold]")
            syntax = Syntax(
                result['traceback'],
                "python",
                theme="monokai",
                line_numbers=False
            )
            console.print(Panel(syntax, border_style="red"))
            console.print()
            
            # Parse and display structured error info
            error_info = parse_error_traceback(result['traceback'])
            
            error_table = Table(show_header=False, box=None)
            error_table.add_column("Property", style="cyan")
            error_table.add_column("Value", style="white")
            
            error_table.add_row("Error Type", error_info['error_type'])
            error_table.add_row("Message", error_info['error_message'])
            
            if error_info['file']:
                error_table.add_row("File", error_info['file'])
            if error_info['line']:
                error_table.add_row("Line", str(error_info['line']))
            if error_info['function']:
                error_table.add_row("Function", error_info['function'])
            
            console.print(Panel(error_table, title="Error Analysis", border_style="yellow"))
            console.print()
        
        # Create comprehensive error report
        report = create_error_report(
            script_path=script,
            execution_result=result,
            include_environment=True
        )
        
        # Save report if requested
        if save_report:
            with open(save_report, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
            console.print(f"[green]✓ Report saved to {save_report}[/green]")
            console.print()
        
        # Submit to serverless endpoint if requested
        if submit:
            try:
                _submit_report(report, mock=mock, wait=wait, create_pr=create_pr)
            except Exception as e:
                console.print()
                console.print(
                    Panel(
                        f"[yellow]⚠ Submission failed[/yellow]\n\n"
                        f"Error: {e}\n\n"
                        f"Report saved locally. You can retry submission later.",
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


def _submit_report(
    report: dict,
    mock: bool = False,
    wait: bool = False,
    create_pr: bool = False
) -> None:
    """
    Submit report to serverless endpoint.
    
    Args:
        report: Error report dictionary
        mock: Use mock mode for testing
        wait: Wait for AI analysis to complete
        create_pr: Create GitHub PR with analysis
    """
    console.print("[bold blue]Submitting report to env-doctor endpoint...[/bold blue]")
    
    # Configure submission client
    config = SubmissionConfig.from_env()
    if mock:
        config.mock_mode = True
    
    # Check if endpoint is configured
    if not mock and not config.api_key:
        console.print()
        console.print(
            Panel(
                "[yellow]⚠ Endpoint not configured[/yellow]\n\n"
                "To submit reports, set the ENV_DOCTOR_API_KEY environment variable.\n"
                "For testing, use --mock flag.\n\n"
                "Example:\n"
                "  export ENV_DOCTOR_API_KEY=your_api_key\n"
                "  env-doctor report-incompatibility test.py",
                title="Configuration Required",
                border_style="yellow"
            )
        )
        return
    
    try:
        # Submit report
        client = SubmissionClient(config)
        
        with console.status("[bold green]Submitting...[/bold green]"):
            submission_id = client.submit_report(report)
        
        console.print()
        console.print(
            Panel(
                f"[green]✓ Report submitted successfully![/green]\n\n"
                f"Submission ID: {submission_id}\n\n"
                f"{'[dim]Using mock mode for testing[/dim]' if mock else 'Your report will help improve env-doctor for the community!'}",
                title="Submission Successful",
                border_style="green"
            )
        )
        console.print()
        
        # Wait for analysis if requested
        if wait:
            console.print("[bold blue]Waiting for AI analysis...[/bold blue]")
            
            with console.status("[bold green]Processing...[/bold green]"):
                result = client.wait_for_completion(submission_id, max_wait=300)
            
            if result:
                console.print()
                _display_analysis_result(result)
                
                # Create PR if requested
                if create_pr:
                    _create_pr_from_result(result, report, mock)
            else:
                console.print()
                console.print(
                    Panel(
                        "[yellow]⚠ Analysis timed out or failed[/yellow]\n\n"
                        f"Check status later with submission ID: {submission_id}",
                        title="Analysis Status",
                        border_style="yellow"
                    )
                )
        else:
            console.print(f"[dim]Check analysis status with submission ID: {submission_id}[/dim]")
            
    except Exception as e:
        raise Exception(f"Failed to submit report: {e}")


def _display_analysis_result(result: dict) -> None:
    """Display AI analysis result."""
    analysis = result.get("analysis", {})
    
    console.print(
        Panel(
            f"[green]✓ AI Analysis Complete![/green]\n\n"
            f"**Root Cause:**\n{analysis.get('root_cause', 'N/A')}\n\n"
            f"**Suggested Fix:**\n{analysis.get('suggested_fix', 'N/A')}\n\n"
            f"**Confidence:** {analysis.get('confidence', 0):.1%}",
            title="AI Analysis",
            border_style="green"
        )
    )
    
    # Display compatibility YAML
    yaml_content = result.get("compatibility_yaml", "")
    if yaml_content:
        console.print()
        console.print("[bold]Generated Compatibility Entry:[/bold]")
        syntax = Syntax(yaml_content, "yaml", theme="monokai", line_numbers=False)
        console.print(Panel(syntax, border_style="blue"))


def _create_pr_from_result(result: dict, report: dict, mock: bool = False) -> None:
    """Create GitHub PR from analysis result."""
    console.print()
    console.print("[bold blue]Creating GitHub pull request...[/bold blue]")
    
    # Configure PR creator
    config = GitHubConfig.from_env()
    if mock:
        config.mock_mode = True
    
    # Check if GitHub is configured
    if not mock and not config.token:
        console.print()
        console.print(
            Panel(
                "[yellow]⚠ GitHub not configured[/yellow]\n\n"
                "To create PRs, set the GITHUB_TOKEN environment variable.\n"
                "For testing, use --mock flag.\n\n"
                "Example:\n"
                "  export GITHUB_TOKEN=your_github_token\n"
                "  env-doctor report-incompatibility test.py --wait --create-pr",
                title="Configuration Required",
                border_style="yellow"
            )
        )
        return
    
    try:
        creator = PRCreator(config)
        analysis = result.get("analysis", {})
        yaml_content = result.get("compatibility_yaml", "")
        
        with console.status("[bold green]Creating PR...[/bold green]"):
            pr_result = creator.create_pr_from_analysis(analysis, report, yaml_content)
        
        console.print()
        console.print(
            Panel(
                f"[green]✓ Pull request created![/green]\n\n"
                f"PR #{pr_result.pr_number}: {pr_result.pr_url}\n\n"
                f"Branch: {pr_result.branch_name}\n\n"
                f"{'[dim]Using mock mode for testing[/dim]' if mock else 'Thank you for contributing to env-doctor!'}",
                title="PR Created",
                border_style="green"
            )
        )
        
    except Exception as e:
        console.print()
        console.print(
            Panel(
                f"[yellow]⚠ PR creation failed[/yellow]\n\n"
                f"Error: {e}\n\n"
                f"You can manually create a PR with the generated YAML.",
                title="PR Error",
                border_style="yellow"
            )
        )


# Made with Bob