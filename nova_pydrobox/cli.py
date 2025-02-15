"""
Interactive CLI demo for nova-pydrobox.

This module provides a command-line interface for demonstrating basic
nova-pydrobox functionality including:
- Dropbox authentication
- File listing with formatted output
- Basic folder operations

The CLI uses Click for command handling and Rich for formatted terminal output.
"""

import click
from rich.console import Console
from rich.table import Table

from nova_pydrobox.auth import Authenticator
from nova_pydrobox.operations import FolderOperations


@click.group()
def cli():
    """
    Nova PyDropbox CLI Demo.

    Provides a command-line interface for basic Dropbox operations.
    Use --help with any command for more information.

    Examples:
        Initialize authentication:
        $ nova-pydrobox authenticate

        List files in root:
        $ nova-pydrobox list-files

        List files in specific folder:
        $ nova-pydrobox list-files /Photos
    """
    pass


@cli.command()
def authenticate():
    """
    Authenticate with Dropbox.

    Initiates the OAuth2 authentication flow and stores the resulting tokens
    securely using the configured storage backend (keyring or encrypted file).

    Returns:
        None

    Note:
        - Opens default browser for authentication
        - Tokens are stored for future use
        - Existing tokens are backed up before refresh
    """
    auth = Authenticator()
    auth.authenticate_dropbox()
    click.echo("Authentication successful!")


@cli.command()
@click.argument("path", default="/")
def list_files(path):
    """
    List files in a Dropbox folder.

    Args:
        path (str): Dropbox folder path to list. Defaults to root ('/').

    Returns:
        None: Prints formatted table to console.

    Note:
        - Displays name, size, and modification time
        - Uses Rich for formatted output
        - Handles both files and folders

    Example:
        List root folder:
        $ nova-pydrobox list-files

        List specific folder:
        $ nova-pydrobox list-files /Documents
    """
    ops = FolderOperations()
    files = ops.list_files(path)

    table = Table(title=f"Files in {path}")
    table.add_column("Name")
    table.add_column("Size")
    table.add_column("Modified")

    for file in files:
        table.add_row(file.name, str(file.size), str(file.client_modified))

    console = Console()
    console.print(table)


if __name__ == "__main__":
    cli()
