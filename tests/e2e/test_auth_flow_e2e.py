"""End-to-end tests for authentication flow."""
import time
from typing import Optional

import dropbox
import pytest
from dropbox.exceptions import AuthError

from nova_pydrobox.auth.authenticator import Authenticator, get_dropbox_client
from nova_pydrobox.auth.token_storage import TokenStorage

@pytest.mark.e2e
def test_token_refresh_flow(e2e_auth):
    """
    Test token refresh functionality.
    
    This test:
    1. Gets initial access token
    2. Forces token refresh
    3. Verifies new token works
    """
    # Get initial client
    client = get_dropbox_client()
    assert client is not None
    
    # Verify initial connection
    account = client.users_get_current_account()
    assert account is not None
    
    # Force token refresh by temporarily invalidating access token
    storage = TokenStorage()
    tokens = storage.get_tokens()
    tokens["access_token"] = "invalid_token"  # Invalidate token to force refresh
    storage.save_tokens(tokens)
    
    # Create new client (should trigger refresh)
    new_client = get_dropbox_client()
    assert new_client is not None
    
    # Verify new connection works
    new_account = new_client.users_get_current_account()
    assert new_account is not None
    assert new_account.account_id == account.account_id

@pytest.mark.e2e
def test_token_storage_security(e2e_auth):
    """
    Test secure token storage and retrieval.
    
    This test:
    1. Verifies tokens are stored securely
    2. Checks token encryption/decryption
    3. Tests token persistence
    """
    # Create new storage instances
    storage1 = TokenStorage(force_fernet=True)  # Force Fernet for consistent testing
    storage2 = TokenStorage(force_fernet=True)
    
    # Get tokens from first instance
    tokens1 = storage1.get_tokens()
    assert tokens1 is not None
    assert "app_key" in tokens1
    assert "app_secret" in tokens1
    assert "refresh_token" in tokens1
    
    # Verify tokens can be read with second instance
    tokens2 = storage2.get_tokens()
    assert tokens2 is not None
    assert tokens2 == tokens1  # Should match exactly

@pytest.mark.e2e
def test_auth_error_handling(e2e_auth, monkeypatch):
    """
    Test authentication error handling.
    
    This test:
    1. Tests invalid token handling
    2. Verifies error reporting
    3. Checks recovery behavior
    """
    def mock_get_dropbox_client() -> Optional[dropbox.Dropbox]:
        """Mock client that always fails authentication."""
        raise AuthError("Test auth error")
    
    # Test with failing client
    monkeypatch.setattr(
        "nova_pydrobox.auth.authenticator.get_dropbox_client",
        mock_get_dropbox_client
    )
    
    auth = Authenticator()
    with pytest.raises(AuthError):
        auth.get_dropbox_client()

@pytest.mark.e2e
def test_auth_session_management(e2e_auth):
    """
    Test authentication session handling.
    
    This test:
    1. Verifies session initialization
    2. Tests multiple client creation
    3. Checks session reuse
    """
    # Create multiple clients
    clients = [get_dropbox_client() for _ in range(3)]
    
    # Verify all clients are valid
    for client in clients:
        assert client is not None
        account = client.users_get_current_account()
        assert account is not None
        
    # Verify all clients have same session
    first_account = clients[0].users_get_current_account()
    for client in clients[1:]:
        account = client.users_get_current_account()
        assert account.account_id == first_account.account_id

@pytest.mark.e2e
def test_token_expiry_handling(e2e_auth):
    """
    Test token expiration handling.
    
    This test:
    1. Tests token lifetime tracking
    2. Verifies expiry detection
    3. Checks automatic refresh
    """
    storage = TokenStorage(token_lifetime=5)  # 5 second lifetime for testing
    auth = Authenticator()
    
    # Store current tokens with short lifetime
    tokens = storage.get_tokens()
    assert tokens is not None
    assert storage.save_tokens(tokens)
    
    # Wait for token expiration
    time.sleep(6)
    
    # Verify tokens are considered expired
    assert not storage._is_token_valid(tokens)
    
    # Get new client (should trigger refresh)
    client = auth.get_dropbox_client()
    assert client is not None
    
    # Verify new client works
    account = client.users_get_current_account()
    assert account is not None

@pytest.mark.e2e
def test_multi_device_token_handling(e2e_auth):
    """
    Test token handling across multiple instances.
    
    This test:
    1. Simulates multiple device access
    2. Tests token consistency
    3. Verifies refresh token sharing
    """
    # Create multiple authenticator instances (simulating different devices)
    auth1 = Authenticator()
    auth2 = Authenticator()
    
    # Get clients from both instances
    client1 = auth1.get_dropbox_client()
    client2 = auth2.get_dropbox_client()
    
    assert client1 is not None
    assert client2 is not None
    
    # Verify both clients access same account
    account1 = client1.users_get_current_account()
    account2 = client2.users_get_current_account()
    
    assert account1.account_id == account2.account_id
