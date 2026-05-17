"""Main entry point for the env-doctor CLI application."""

import typer
from rich.console import Console

from env_doctor import __version__
from env_doctor.cli import (
    check,
    inspect,
    patch,
    recommend,
    repo,
    report,
    submit_stack,
    update,
    vram,
)

app = typer.Typer(
    name="env-doctor",
    help="Runtime compatibility intelligence for ML environments",
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"env-doctor version: {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """
    env-doctor: Runtime compatibility intelligence for ML environments.
    
    A comprehensive tool for managing Python package dependencies, detecting
    incompatibilities, and optimizing ML/AI development environments.
    
    Commands:
      update-db              Update local database from repository
      repo                   Manage intelligence repositories
      inspect                Scan and display environment information
      check                  Check compatibility of dependencies
      recommend              Recommend stable package stacks
      vram                   Estimate VRAM requirements for models
      patch                  Fix incompatibilities in dependency files
      report-incompatibility Report errors from script execution
    
    Use --help with any command to see detailed usage information.
    """
    pass


# Register all CLI commands
app.command(name="update-db")(update.update_db)
app.add_typer(repo.app, name="repo")
app.command(name="inspect")(inspect.inspect_env)
app.command(name="check")(check.check_compatibility)
app.command(name="recommend")(recommend.recommend_stack)
app.command(name="vram")(vram.estimate_vram)
app.command(name="patch")(patch.patch_dependencies)
app.command(name="report-incompatibility")(report.report_incompatibility)
app.command(name="submit-stack")(submit_stack.submit_stack)


if __name__ == "__main__":
    app()

# Made with Bob
