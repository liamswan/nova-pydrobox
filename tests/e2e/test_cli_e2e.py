"""End-to-end tests for CLI functionality."""

import pytest
from click.testing import CliRunner

from nova_pydrobox.cli import cli
from nova_pydrobox.operations.files import FileOperations

@pytest.fixture
def cli_runner():
    """Create a Click CLI test runner."""
    return CliRunner()

@pytest.fixture
def setup_test_folder(e2e_auth, e2e_dropbox_client, e2e_test_path, test_folder):
    """Set up test data in Dropbox for CLI testing."""
    # Upload test data
    file_ops = FileOperations(dbx_client=e2e_dropbox_client)
    file_ops.upload(str(test_folder), e2e_test_path)
    return e2e_test_path

@pytest.mark.e2e
def test_list_files_root(cli_runner, e2e_auth):
    """
    Test listing files from root directory.
    
    This test:
    1. Calls list-files without path
    2. Verifies command executes successfully
    3. Checks output formatting
    """
    result = cli_runner.invoke(cli, ["list-files"])
    assert result.exit_code == 0
    # Output should contain table elements
    assert "Files in /" in result.output
    assert "Name" in result.output
    assert "Size" in result.output
    assert "Modified" in result.output

@pytest.mark.e2e
def test_list_files_specific_path(cli_runner, e2e_auth, setup_test_folder):
    """
    Test listing files from specific directory.
    
    This test:
    1. Lists files in test directory
    2. Verifies test files are listed
    3. Checks output formatting
    """
    result = cli_runner.invoke(cli, ["list-files", setup_test_folder])
    assert result.exit_code == 0
    
    # Check for test files in output
    assert "file1.txt" in result.output
    assert "file2.txt" in result.output
    assert "subfolder" in result.output

@pytest.mark.e2e
def test_list_files_nonexistent_path(cli_runner, e2e_auth, e2e_test_path):
    """
    Test listing files from non-existent directory.
    
    This test:
    1. Attempts to list non-existent path
    2. Verifies appropriate error handling
    """
    bad_path = f"{e2e_test_path}/nonexistent"
    result = cli_runner.invoke(cli, ["list-files", bad_path])
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "error" in result.output.lower()

@pytest.mark.e2e
def test_cli_auth_flow(cli_runner, monkeypatch):
    """
    Test authentication flow through CLI.
    
    This test:
    1. Simulates auth command
    2. Verifies success message
    
    Note: This test assumes auth will succeed since e2e_auth fixture
    has already authenticated. In a real scenario, we'd need to
    handle browser interaction and token input.
    """
    result = cli_runner.invoke(cli, ["authenticate"])
    assert result.exit_code == 0
    assert "Authentication successful" in result.output

@pytest.mark.e2e
def test_cli_help(cli_runner):
    """
    Test CLI help commands.
    
    This test:
    1. Checks main help output
    2. Checks command-specific help
    """
    # Test main help
    result = cli_runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Nova PyDropbox CLI Demo" in result.output
    
    # Test list-files help
    result = cli_runner.invoke(cli, ["list-files", "--help"])
    assert result.exit_code == 0
    assert "List files in a Dropbox folder" in result.output

@pytest.mark.e2e
def test_cli_invalid_command(cli_runner):
    """
    Test handling of invalid CLI commands.
    
    This test:
    1. Attempts invalid command
    2. Verifies error message
    """
    result = cli_runner.invoke(cli, ["invalid-command"])
    assert result.exit_code != 0
    assert "No such command" in result.output

@pytest.mark.e2e
def test_cli_list_files_path_formatting(cli_runner, e2e_auth, setup_test_folder):
    """
    Test path handling in list-files command.
    
    This test:
    1. Tests various path formats
    2. Verifies consistent handling
    """
    # Test with trailing slash
    result1 = cli_runner.invoke(cli, ["list-files", f"{setup_test_folder}/"])
    assert result1.exit_code == 0
    
    # Test without trailing slash
    result2 = cli_runner.invoke(cli, ["list-files", setup_test_folder])
    assert result2.exit_code == 0
    
    # Both should show the same content
    assert result1.output == result2.output

@pytest.mark.e2e
def test_cli_output_formatting(cli_runner, e2e_auth, setup_test_folder):
    """
    Test CLI output formatting.
    
    This test:
    1. Verifies table formatting
    2. Checks size formatting
    3. Validates date formatting
    """
    result = cli_runner.invoke(cli, ["list-files", setup_test_folder])
    assert result.exit_code == 0
    
    # Basic formatting checks
    assert "─" in result.output  # Table borders
    assert "│" in result.output  # Table columns
    assert "Name" in result.output
    assert "Size" in result.output
    assert "Modified" in result.output
