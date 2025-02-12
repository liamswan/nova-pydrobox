"""Tests for the authenticator module."""

from unittest.mock import MagicMock, patch

import dropbox
import pytest

from nova_pydrobox.auth.authenticator import (
    authenticate_dropbox,
    get_dropbox_client,
    setup_credentials,
)


@pytest.fixture
def mock_token_storage():
    with patch("nova_pydrobox.auth.authenticator.TokenStorage") as mock:
        storage_instance = MagicMock()
        mock.return_value = storage_instance
        yield storage_instance


@pytest.fixture
def mock_dropbox_flow():
    with patch("dropbox.DropboxOAuth2FlowNoRedirect") as mock:
        flow_instance = MagicMock()
        mock.return_value = flow_instance
        yield flow_instance


def test_setup_credentials(monkeypatch):
    """Test the setup_credentials function with valid input."""
    print("DEBUG: Starting test_setup_credentials")

    # Mock user input - first two are for "Press Enter" prompts
    inputs = [
        "",
        "",
        "test_key",
        "test_secret",
    ]  # First two empty strings for Enter presses
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: (print(f"DEBUG: Prompted with: {prompt}"), inputs.pop(0))[1],
    )
    print("DEBUG: User input mocked")

    # Mock webbrowser
    mock_browser = MagicMock()
    monkeypatch.setattr(
        "webbrowser.open",
        lambda url: (
            print(f"DEBUG: Opening web browser with URL: {url}"),
            mock_browser(url),
        )[1],
    )
    print("DEBUG: Webbrowser mocked")

    app_key, app_secret = setup_credentials()
    print("DEBUG: setup_credentials returned successfully")

    assert app_key == "test_key"
    assert app_secret == "test_secret"
    mock_browser.assert_called_once_with("https://www.dropbox.com/developers/apps")
    print("DEBUG: test_setup_credentials completed successfully")


def test_authenticate_dropbox_failure(
    mock_token_storage, mock_dropbox_flow, monkeypatch
):
    """Test failed Dropbox authentication."""
    # Mock user input including setup_credentials prompts
    inputs = [
        "",  # First Enter press
        "",  # Second Enter press
        "test_key",  # App key
        "test_secret",  # App secret
        "test_auth_code",  # Auth code
    ]
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: (print(f"DEBUG: Prompted with: {prompt}"), inputs.pop(0))[1],
    )

    # Mock webbrowser
    mock_browser = MagicMock()
    monkeypatch.setattr("webbrowser.open", mock_browser)

    # Configure mock flow with proper AuthError initialization
    mock_dropbox_flow.finish.side_effect = dropbox.exceptions.AuthError(
        error={"error_summary": "Auth failed"}, request_id="test_request_id"
    )

    result = authenticate_dropbox(force_reauth=True)

    assert result is False
    mock_token_storage.save_tokens.assert_not_called()


def test_get_dropbox_client_success(mock_token_storage):
    """Test successful Dropbox client initialization."""
    # Configure mock storage
    mock_token_storage.get_tokens.return_value = {
        "app_key": "test_key",
        "app_secret": "test_secret",
        "refresh_token": "test_refresh_token",
    }

    with patch("dropbox.Dropbox") as mock_dropbox:
        dbx_instance = MagicMock()
        mock_dropbox.return_value = dbx_instance

        client = get_dropbox_client()

        assert client is not None
        assert client == dbx_instance
        mock_dropbox.assert_called_once_with(
            oauth2_refresh_token="test_refresh_token",
            app_key="test_key",
            app_secret="test_secret",
        )


def test_get_dropbox_client_no_credentials(mock_token_storage):
    """Test Dropbox client initialization with no credentials."""
    # Configure mock storage to return no tokens
    mock_token_storage.get_tokens.return_value = None

    client = get_dropbox_client()

    assert client is None


def test_get_dropbox_client_auth_error(mock_token_storage):
    """Test Dropbox client initialization with auth error."""
    # Configure mock storage
    mock_token_storage.get_tokens.return_value = {
        "app_key": "test_key",
        "app_secret": "test_secret",
        "refresh_token": "test_refresh_token",
    }

    with patch("dropbox.Dropbox") as mock_dropbox:
        dbx_instance = MagicMock()
        # First call to users_get_current_account raises AuthError
        dbx_instance.users_get_current_account.side_effect = (
            dropbox.exceptions.AuthError(
                error={"error_summary": "Auth failed"}, request_id="test_request_id"
            )
        )
        mock_dropbox.return_value = dbx_instance

        client = get_dropbox_client()

        assert client is not None
        # Verify that refresh_access_token was called
        dbx_instance.refresh_access_token.assert_called_once()
