"""Interactive CLI demo for nova-pydrobox."""

import click
from rich.console import Console
from rich.table import Table

from nova_pydrobox.auth import Authenticator
from nova_pydrobox.operations import FolderOperations


@click.group()
def cli():
    """Nova PyDropbox CLI Demo"""
    pass


@cli.command()
def authenticate():
    """Authenticate with Dropbox"""
    auth = Authenticator()
    auth.authenticate_dropbox()
    click.echo("Authentication successful!")


@cli.command()
@click.argument("path", default="/")
def list_files(path):
    """List files in a Dropbox folder"""
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
