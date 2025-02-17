"""Tests for the authenticator module."""

import dropbox
import pytest

from nova_pydrobox.auth.authenticator import (
    Authenticator,
    authenticate_dropbox,
    get_dropbox_client,
    main,
    setup_credentials,
)


@pytest.fixture
def mock_webbrowser(mocker):
    return mocker.patch("webbrowser.open")


@pytest.fixture
def mock_token_storage(mocker):
    storage = mocker.Mock()
    storage.get_access_token.return_value = "test_access_token"
    storage.get_refresh_token.return_value = "test_refresh_token"
    return storage


@pytest.fixture
def mock_dropbox_flow(mocker):
    flow_instance = mocker.MagicMock()
    mocker.patch("dropbox.DropboxOAuth2FlowNoRedirect", return_value=flow_instance)
    return flow_instance


@pytest.fixture
def mock_auth(mocker):
    """Mock Authenticator instance."""
    return mocker.patch("nova_pydrobox.auth.authenticator.Authenticator")


@pytest.fixture
def mock_storage(mocker):
    """Mock TokenStorage instance."""
    return mocker.patch("nova_pydrobox.auth.authenticator.TokenStorage").return_value


@pytest.fixture
def mock_input(mocker):
    return mocker.patch("builtins.input")


@pytest.fixture
def patched_token_storage(mocker):
    storage_instance = mocker.MagicMock()
    storage_instance.get_tokens.return_value = {"dummy": "token"}
    mocker.patch("nova_pydrobox.auth.authenticator.TokenStorage", return_value=storage_instance)
    return storage_instance


def test_setup_credentials(mocker, monkeypatch):
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
    mock_browser = mocker.MagicMock()
    mock_open = mocker.patch("webbrowser.open", side_effect=mock_browser)
    print("DEBUG: Webbrowser mocked")

    app_key, app_secret = setup_credentials()
    print("DEBUG: setup_credentials returned successfully")

    assert app_key == "test_key"
    assert app_secret == "test_secret"
    mock_open.assert_called_once_with("https://www.dropbox.com/developers/apps")
    print("DEBUG: test_setup_credentials completed successfully")


def test_authenticate_dropbox_failure(
    mocker, mock_token_storage, mock_dropbox_flow, monkeypatch
):
    """Test failed Dropbox authentication."""
    # Mock TokenStorage
    storage_mock = mocker.patch("nova_pydrobox.auth.authenticator.TokenStorage")
    storage_mock.return_value = mock_token_storage

    # Mock user input including setup_credentials prompts
    inputs = [
        "",  # First Enter press
        "",  # Second Enter press
        "test_key",  # App key
        "test_secret",  # App secret
        "test_auth_code",  # Auth code
    ]
    monkeypatch.setattr("builtins.input", lambda prompt: inputs.pop(0))
    mocker.patch("webbrowser.open")

    # Configure mock flow to raise an AuthError
    mock_dropbox_flow.finish.side_effect = dropbox.exceptions.AuthError(
        error={"error_summary": "Auth failed"}, request_id="test_request_id"
    )

    result = authenticate_dropbox(force_reauth=True)
    assert result is False
    mock_token_storage.save_tokens.assert_not_called()


def test_authenticate_dropbox_success(mocker, monkeypatch):
    """Test successful Dropbox authentication."""
    # Mock TokenStorage class
    mock_storage = mocker.MagicMock()
    mock_storage.save_tokens.return_value = True
    mocker.patch(
        "nova_pydrobox.auth.authenticator.TokenStorage",
        return_value=mock_storage
    )

    auth = Authenticator()

    # Rest of the test setup...
    inputs = [
        "",
        "",
        "test_key",
        "test_secret",
        "test_auth_code",
    ]
    monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0))
    mocker.patch("webbrowser.open")

    # Mock OAuth flow
    mock_flow = mocker.MagicMock()
    mock_result = mocker.MagicMock()
    mock_result.access_token = "test_access"
    mock_result.refresh_token = "test_refresh"
    mock_flow.finish.return_value = mock_result
    mocker.patch(
        "dropbox.DropboxOAuth2FlowNoRedirect",
        return_value=mock_flow
    )

    result = auth.authenticate_dropbox(force_reauth=True)

    assert result is True
    mock_storage.save_tokens.assert_called_once_with(
        {
            "app_key": "test_key",
            "app_secret": "test_secret",
            "access_token": "test_access",
            "refresh_token": "test_refresh",
        }
    )


def test_authenticate_dropbox_token_storage_failure(
    mocker, mock_token_storage, mock_dropbox_flow, monkeypatch
):
    """Test authentication with token storage failure."""
    mocker.patch("nova_pydrobox.auth.authenticator.TokenStorage", return_value=mock_token_storage)
    auth = Authenticator()  # Now uses patched TokenStorage

    # Mock credentials setup
    mock_credentials = ("test_key", "test_secret")
    monkeypatch.setattr(auth, "setup_credentials", lambda: mock_credentials)

    # Mock OAuth flow
    mock_result = mocker.MagicMock()
    mock_result.access_token = "test_access"
    mock_result.refresh_token = "test_refresh"
    mock_dropbox_flow.finish.return_value = mock_result

    # Simulate token storage failure
    mock_token_storage.save_tokens.return_value = False

    result = auth.authenticate_dropbox(force_reauth=True)
    assert result is False


def test_get_dropbox_client_success(mocker):
    """Test successful Dropbox client initialization."""
    mock_storage = mocker.MagicMock()
    mock_storage.get_tokens.return_value = {
        "app_key": "test_key",
        "app_secret": "test_secret",
        "refresh_token": "test_refresh",
    }

    mocker.patch(
        "nova_pydrobox.auth.authenticator.TokenStorage",
        return_value=mock_storage
    )

    mock_dropbox = mocker.patch("dropbox.Dropbox")
    mock_instance = mocker.MagicMock()
    mock_dropbox.return_value = mock_instance

    client = get_dropbox_client()

    assert client is not None
    assert client == mock_instance
    mock_dropbox.assert_called_once_with(
        oauth2_refresh_token="test_refresh",
        app_key="test_key",
        app_secret="test_secret",
    )


def test_get_dropbox_client_no_credentials(mocker, mock_token_storage):
    """Test Dropbox client initialization with no credentials."""
    # Configure mock storage to return no tokens
    mock_token_storage.get_tokens.return_value = None

    mocker.patch(
        "nova_pydrobox.auth.authenticator.TokenStorage",
        return_value=mock_token_storage
    )
    client = get_dropbox_client()

    assert client is None


def test_get_dropbox_client_auth_error(mocker, mock_token_storage):
    """Test Dropbox client initialization with auth error."""
    mock_token_storage.get_tokens.return_value = {
        "app_key": "test_key",
        "app_secret": "test_secret",
        "refresh_token": "test_refresh_token",
    }
    
    mocker.patch(
        "nova_pydrobox.auth.authenticator.TokenStorage",
        return_value=mock_token_storage
    )
    auth = Authenticator()

    dbx_instance = mocker.MagicMock()
    dbx_instance.users_get_current_account.side_effect = (
        dropbox.exceptions.AuthError(
            error={"error_summary": "Auth failed"}, request_id="test_request_id"
        )
    )
    mocker.patch("dropbox.Dropbox", return_value=dbx_instance)

    client = auth.get_dropbox_client()
    assert client is None
    assert dbx_instance.users_get_current_account.called


def test_setup_credentials_retry(monkeypatch, mock_webbrowser):
    """
    Test setup_credentials retries until valid inputs are provided.
    User first provides empty inputs then valid ones.
    """
    # Provide two Enter prompts, then two empty credential attempts, then valid ones.
    inputs = [
        "",  # First Enter press
        "",  # Second Enter press
        "",  # First attempt app key (empty)
        "",  # First attempt app secret (empty)
        "final_key",  # Second attempt app key
        "final_secret",  # Second attempt app secret
    ]
    monkeypatch.setattr("builtins.input", lambda prompt: inputs.pop(0))
    app_key, app_secret = setup_credentials()
    assert app_key == "final_key"
    assert app_secret == "final_secret"


def test_authenticate_dropbox_unexpected_exception(monkeypatch):
    """
    Test authentication when an unexpected exception occurs during setup_credentials.
    """
    auth = Authenticator()

    # Force unexpected exception by patching setup_credentials to raise Exception.
    def raise_exception():
        raise Exception("Unexpected error")

    monkeypatch.setattr(auth, "setup_credentials", raise_exception)

    result = auth.authenticate_dropbox(force_reauth=True)
    assert result is False


def test_get_dropbox_client_incomplete_credentials(mocker):
    """
    Test get_dropbox_client when credentials are missing required fields.
    """
    incomplete_creds = {
        "app_key": "incomplete_key"
    }  # Missing app_secret and refresh_token

    storage_instance = mocker.MagicMock()
    storage_instance.get_tokens.return_value = incomplete_creds
    mocker.patch(
        "nova_pydrobox.auth.authenticator.TokenStorage",
        return_value=storage_instance
    )

    client = get_dropbox_client()
    assert client is None


def test_main_keyboard_interrupt(monkeypatch):
    """
    Test main function handling KeyboardInterrupt during user input.
    """
    # Simulate KeyboardInterrupt on input call.
    monkeypatch.setattr(
        "builtins.input", lambda prompt="": (_ for _ in ()).throw(KeyboardInterrupt())
    )
    with pytest.raises(KeyboardInterrupt):
        main()


def test_main_with_no_storage_token(mocker):
    """
    Test main function behavior when TokenStorage.get_tokens returns None.
    Expect the authentication flow to be triggered without accessing the keychain.
    """
    # Mock TokenStorage
    auth_instance = mocker.MagicMock()
    auth_instance.authenticate_dropbox.return_value = True
    mocker.patch("nova_pydrobox.auth.authenticator.Authenticator", return_value=auth_instance)

    storage_instance = mocker.MagicMock()
    storage_instance.get_tokens.return_value = None
    mocker.patch(
        "nova_pydrobox.auth.authenticator.TokenStorage",
        return_value=storage_instance
    )

    # Simulate user choosing to authenticate by returning "y" on input.
    mocker.patch("builtins.input", return_value="y")

    main()
    auth_instance.authenticate_dropbox.assert_called_once()


def test_main_with_existing_tokens_force_reauth(mocker):
    """Test main function when user forces re-authentication with existing tokens."""
    # Mock TokenStorage
    auth_instance = mocker.MagicMock()
    auth_instance.authenticate_dropbox.return_value = True
    mocker.patch("nova_pydrobox.auth.authenticator.Authenticator", return_value=auth_instance)

    storage_instance = mocker.MagicMock()
    storage_instance.get_tokens.return_value = {"some": "tokens"}
    mocker.patch(
        "nova_pydrobox.auth.authenticator.TokenStorage",
        return_value=storage_instance
    )

    mocker.patch("builtins.input", return_value="y")
    
    main()
    auth_instance.authenticate_dropbox.assert_called_once_with(force_reauth=True)


def test_setup_credentials_with_empty_inputs(mocker, mock_webbrowser):
    """Test setup_credentials function with empty inputs followed by valid inputs."""
    inputs = [
        "",  # First Enter press
        "",  # Second Enter press
        "",  # Empty app key
        "",  # Empty app secret
        "valid_key",  # Valid app key
        "valid_secret",  # Valid app secret
    ]
    mocker.patch("builtins.input", side_effect=inputs)

    app_key, app_secret = setup_credentials()

    assert app_key == "valid_key"
    assert app_secret == "valid_secret"


def test_authenticate_dropbox_existing_tokens_no_force(mocker, mock_token_storage):
    """Test authenticate_dropbox with existing tokens and no force reauth."""
    # Mock TokenStorage
    mocker.patch(
        "nova_pydrobox.auth.authenticator.TokenStorage",
        return_value=mock_token_storage
    )

    # Set up the mock return value
    mock_token_storage.get_tokens.return_value = {
        "app_key": "existing_key",
        "app_secret": "existing_secret",
        "refresh_token": "existing_refresh",
    }

    auth = Authenticator()
    result = auth.authenticate_dropbox(force_reauth=False)

    assert result is True
    mock_token_storage.get_tokens.assert_called_once()


def test_authenticate_dropbox_empty_auth_code(
    mocker, mock_token_storage, mock_dropbox_flow, monkeypatch
):
    """Test authentication with empty auth code input."""
    auth = Authenticator()

    # Mock inputs including empty auth code then valid code
    inputs = [
        "",  # First Enter
        "",  # Second Enter
        "test_key",
        "test_secret",
        "",  # Empty auth code
        "valid_code",  # Valid auth code
    ]
    monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0))
    mocker.patch("webbrowser.open")

    # Mock successful token storage
    mock_token_storage.save_tokens.return_value = True

    # Mock OAuth result
    mock_result = mocker.MagicMock()
    mock_result.access_token = "test_access"
    mock_result.refresh_token = "test_refresh"
    mock_dropbox_flow.finish.return_value = mock_result

    result = auth.authenticate_dropbox(force_reauth=True)
    assert result is True


def test_get_dropbox_client_refresh_token_exception(mocker, mock_token_storage):
    """Test get_dropbox_client when refresh_access_token raises an exception."""
    mocker.patch(
        "nova_pydrobox.auth.authenticator.TokenStorage",
        return_value=mock_token_storage
    )
    mock_token_storage.get_tokens.return_value = {
        "app_key": "test_key",
        "app_secret": "test_secret",
        "refresh_token": "test_refresh",
    }

    dbx_instance = mocker.MagicMock()
    dbx_instance.users_get_current_account.side_effect = (
        dropbox.exceptions.AuthError(
            error={"error_summary": "Auth failed"}, request_id="test_request_id"
        )
    )
    mocker.patch("dropbox.Dropbox", return_value=dbx_instance)

    client = get_dropbox_client()

    assert client is None
    assert dbx_instance.users_get_current_account.called


def test_authenticator_failed_connection(mocker, mock_token_storage):
    """Test Dropbox client initialization with connection error."""
    mocker.patch(
        "nova_pydrobox.auth.authenticator.TokenStorage",
        return_value=mock_token_storage
    )
    auth = Authenticator()
    mock_token_storage.get_tokens.return_value = {
        "app_key": "test_key",
        "app_secret": "test_secret",
        "refresh_token": "test_refresh",
    }

    dbx_instance = mocker.MagicMock()
    dbx_instance.users_get_current_account.side_effect = Exception(
        "Connection failed"
    )
    mocker.patch("dropbox.Dropbox", return_value=dbx_instance)

    client = auth.get_dropbox_client()
    assert client is None


def test_main_skip_reauth(mocker):
    """Test main function when user skips re-authentication."""
    # Mock TokenStorage
    auth_instance = mocker.MagicMock()
    mocker.patch("nova_pydrobox.auth.authenticator.Authenticator", return_value=auth_instance)

    storage_instance = mocker.MagicMock()
    storage_instance.get_tokens.return_value = {"some": "tokens"}
    mocker.patch(
        "nova_pydrobox.auth.authenticator.TokenStorage",
        return_value=storage_instance
    )

    mocker.patch("builtins.input", return_value="n")
    
    main()
    auth_instance.authenticate_dropbox.assert_not_called()


def test_authenticate_dropbox_setup_error(mocker, mock_token_storage):
    """Test authentication when setup_credentials fails."""
    auth = Authenticator()

    mocker.patch.object(
        auth,
        "setup_credentials",
        side_effect=Exception("Setup failed")
    )
    result = auth.authenticate_dropbox(force_reauth=True)
    assert result is False


def test_main_with_no_tokens(mocker):
    """Test main function with no existing tokens."""
    # Mock TokenStorage
    auth_instance = mocker.MagicMock()
    auth_instance.authenticate_dropbox.return_value = True
    mocker.patch("nova_pydrobox.auth.authenticator.Authenticator", return_value=auth_instance)

    storage_instance = mocker.MagicMock()
    storage_instance.get_tokens.return_value = None
    mocker.patch(
        "nova_pydrobox.auth.authenticator.TokenStorage",
        return_value=storage_instance
    )

    mocker.patch("builtins.input", return_value="y")
    
    main()
    auth_instance.authenticate_dropbox.assert_called_once()


def test_main_with_auth_failure(mocker):
    """Test main function when authentication fails."""
    # Mock TokenStorage
    auth_instance = mocker.MagicMock()
    auth_instance.authenticate_dropbox.return_value = False
    mocker.patch("nova_pydrobox.auth.authenticator.Authenticator", return_value=auth_instance)

    storage_instance = mocker.MagicMock()
    storage_instance.get_tokens.return_value = None
    mocker.patch(
        "nova_pydrobox.auth.authenticator.TokenStorage",
        return_value=storage_instance
    )

    mocker.patch("builtins.input", return_value="y")
    
    main()
    auth_instance.authenticate_dropbox.assert_called_once()


def test_setup_credentials_empty_input(mocker, mock_webbrowser):
    """Test handling of empty credentials input."""
    inputs = [
        "",  # First Enter press
        "",  # Second Enter press
        "",  # Empty app key
        "",  # Empty app secret
        "valid_key",  # Valid app key
        "valid_secret",  # Valid app secret
    ]
    mocker.patch("builtins.input", side_effect=inputs)

    app_key, app_secret = setup_credentials()

    assert app_key == "valid_key"
    assert app_secret == "valid_secret"


def test_setup_credentials_browser_error(mocker):
    """Test setup_credentials when browser fails to open.
    Covers line 48-52 error handling in setup_credentials"""

    # Mock webbrowser at module level
    mocker.patch("webbrowser.open", side_effect=Exception("Browser error"))

    inputs = [
        "",  # First Enter
        "",  # Second Enter
        "test_key",
        "test_secret",
    ]
    mocker.patch("builtins.input", side_effect=inputs)

    # Function should still complete despite browser error
    app_key, app_secret = setup_credentials()
    assert app_key == "test_key"
    assert app_secret == "test_secret"


def test_authenticate_dropbox_auth_code_retry(
    mocker, mock_token_storage, mock_dropbox_flow, monkeypatch
):
    """Test authentication with invalid auth code followed by valid code.
    Covers lines 82-83 error handling in authenticate_dropbox"""

    auth = Authenticator()

    # Setup mock flow to fail first time, succeed second time
    mock_result = mocker.MagicMock()
    mock_result.access_token = "test_access"
    mock_result.refresh_token = "test_refresh"

    mock_dropbox_flow.finish.side_effect = [
        dropbox.exceptions.AuthError(
            error={"error_summary": "Invalid auth code"},
            request_id="test_request_id",
        ),
        mock_result,
    ]

    inputs = [
        "",  # First Enter
        "",  # Second Enter
        "test_key",
        "test_secret",
        "invalid_code",  # First attempt fails
        "valid_code",  # Second attempt succeeds
    ]
    monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0))
    mocker.patch("webbrowser.open")

    mock_token_storage.save_tokens.return_value = True

    result = auth.authenticate_dropbox(force_reauth=True)
    assert result is True


def test_authenticate_dropbox_token_save_retry(
    mocker, mock_token_storage, mock_dropbox_flow, monkeypatch
):
    """Test authentication with token storage failure followed by success.
    Covers additional error handling paths in authenticate_dropbox"""
    mocker.patch(
        "nova_pydrobox.auth.authenticator.TokenStorage",
        return_value=mock_token_storage
    )
    auth = Authenticator()

    mock_result = mocker.MagicMock()
    mock_result.access_token = "test_access"
    mock_result.refresh_token = "test_refresh"
    mock_dropbox_flow.finish.return_value = mock_result

    # Configure storage to fail first time, succeed second time
    mock_token_storage.save_tokens.side_effect = [False, True]

    inputs = [
        "",  # First Enter
        "",  # Second Enter
        "test_key",
        "test_secret",
        "valid_code",
    ]
    monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0))
    mocker.patch("webbrowser.open")

    result = auth.authenticate_dropbox(force_reauth=True)
    assert result is True
    assert mock_token_storage.save_tokens.call_count == 2


def test_main_error_handling(mocker):
    """Test main function error handling."""
    # Mock TokenStorage
    auth_instance = mocker.MagicMock()
    auth_instance.authenticate_dropbox.side_effect = Exception("Test error")
    mocker.patch("nova_pydrobox.auth.authenticator.Authenticator", return_value=auth_instance)

    storage_instance = mocker.MagicMock()
    storage_instance.get_tokens.return_value = None
    mocker.patch(
        "nova_pydrobox.auth.authenticator.TokenStorage",
        return_value=storage_instance
    )

    mocker.patch("builtins.input", return_value="y")
    
    with pytest.raises(Exception):
        main()
