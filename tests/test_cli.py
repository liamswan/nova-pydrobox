# tests/test_cli.py
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from nova_pydrobox.cli import authenticate, cli, list_files


@pytest.fixture(autouse=True)
def mock_token_storage(mocker):
    """Mock TokenStorage to prevent keychain access during tests."""
    return mocker.patch("nova_pydrobox.auth.TokenStorage")


@pytest.fixture
def mock_dropbox_flow(mocker):
    """Mock DropboxOAuth2FlowNoRedirect."""
    mock_flow = mocker.patch("dropbox.oauth.DropboxOAuth2FlowNoRedirect")
    mock_flow_instance = mock_flow.return_value
    mock_flow_instance.start.return_value = "http://fake-auth-url"
    return mock_flow


def test_cli_group():
    """Test CLI group base command."""
    runner = CliRunner()
    result = runner.invoke(cli)
    assert result.exit_code == 0


@pytest.mark.parametrize("command", [authenticate, list_files])
def test_cli_commands_help(command):
    """Test help output for CLI commands."""
    runner = CliRunner()
    result = runner.invoke(command, ["--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output


def test_authenticate_command(mocker):
    """Test authenticate command."""
    mock_auth_class = mocker.patch("nova_pydrobox.cli.Authenticator")
    mock_auth_instance = mock_auth_class.return_value
    mock_auth_instance.authenticate_dropbox.return_value = True

    runner = CliRunner()
    result = runner.invoke(authenticate)

    assert result.exit_code == 0
    mock_auth_instance.authenticate_dropbox.assert_called_once()


def test_list_files_command(mocker):
    """Test list_files command."""
    # Create a mock file object
    mock_file = MagicMock()
    mock_file.name = "test.txt"
    mock_file.size = 100
    mock_file.client_modified = "2024-01-01 00:00:00"

    # Mock the entire chain at once
    mock_ops = mocker.patch("nova_pydrobox.cli.FolderOperations")
    mock_ops.return_value.list_files.return_value = [mock_file]

    # Mock token storage
    mocker.patch(
        "nova_pydrobox.auth.TokenStorage.get_tokens",
        return_value={"app_key": "test", "app_secret": "test", "refresh_token": "test"},
    )

    runner = CliRunner()
    result = runner.invoke(list_files, ["/test"])

    # Debug output if needed
    if result.exit_code != 0:
        print(f"Error: {result.exception}")

    assert result.exit_code == 0
    mock_ops.return_value.list_files.assert_called_once_with("/test")


def test_authenticate_dropbox_success(mock_token_storage, mock_dropbox_flow, mocker):
    """Test successful Dropbox authentication."""
    # Mock the Authenticator class instead of creating an instance
    mock_auth = mocker.patch("nova_pydrobox.cli.Authenticator")
    mock_auth_instance = mock_auth.return_value

    # Set up the mock responses
    mock_auth_instance.setup_credentials.return_value = ("test_key", "test_secret")
    mock_auth_instance.authenticate_dropbox.return_value = True

    # Mock token storage
    mock_token_storage.return_value.save_tokens.return_value = True

    # Create mock OAuth result
    mock_result = MagicMock()
    mock_result.access_token = "test_access"
    mock_result.refresh_token = "test_refresh"
    mock_dropbox_flow.return_value.finish.return_value = mock_result

    result = mock_auth_instance.authenticate_dropbox(force_reauth=True)
    assert result is True
    mock_auth_instance.authenticate_dropbox.assert_called_once_with(force_reauth=True)
