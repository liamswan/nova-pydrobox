"""Tests for the token storage module."""

import json
import logging
from pathlib import Path  # Remove 'os' import as it's unused

import keyring
import pytest
from cryptography.fernet import Fernet

from nova_pydrobox.auth.token_storage import TokenStorage


@pytest.fixture
def test_tokens():
    return {
        "app_key": "test_key",
        "app_secret": "test_secret",
        "access_token": "test_access",
        "refresh_token": "test_refresh",
    }


@pytest.fixture
def mock_fernet(mocker):
    mock = mocker.Mock()
    mock.encrypt.return_value = b"encrypted_data"
    mock.decrypt.return_value = json.dumps(
        {
            "app_key": "test_key",
            "app_secret": "test_secret",
            "access_token": "test_access",
            "refresh_token": "test_refresh",
        }
    ).encode()
    return mock


@pytest.fixture
def mock_config_dir(mocker):
    mock_home = mocker.patch("pathlib.Path.home")
    mock_home.return_value = Path("/mock/home")
    yield Path("/mock/home/.config/nova-pydropbox")


def test_init_with_working_keyring(mocker):
    """Test TokenStorage initialization with working keyring."""
    mocker.patch.object(TokenStorage, "_test_keyring", return_value=True)
    storage = TokenStorage(force_fernet=False)  # Force keyring usage
    assert storage.use_keyring is True


def test_init_with_broken_keyring(mocker):
    """Test TokenStorage initialization with non-working keyring."""
    mocker.patch.object(TokenStorage, "_test_keyring", return_value=False)
    storage = TokenStorage()
    assert storage.use_keyring is False


def test_save_tokens_keyring_success(test_tokens, mocker):
    """Test saving tokens using keyring backend."""
    storage = TokenStorage(force_fernet=False)  # Force keyring usage
    storage.use_keyring = True  # Ensure keyring is used

    mock_set = mocker.patch("keyring.set_password")
    result = storage.save_tokens(test_tokens)
    assert result is True
    assert mock_set.call_count == len(test_tokens)

    # Check that each token is stored with proper encoding
    for key, value in test_tokens.items():
        encoded_value = storage._encode_value(value)
        mock_set.assert_any_call(storage.service_name, key, encoded_value)


def test_save_tokens_keyring_failure(test_tokens, mocker):
    """Test saving tokens using keyring backend with failure."""
    storage = TokenStorage()
    storage.use_keyring = True

    # Mock both keyring.set_password to fail and _fernet_save_tokens to fail
    mocker.patch("keyring.set_password", side_effect=keyring.errors.PasswordSetError)
    mocker.patch.object(storage, "_fernet_save_tokens", return_value=False)
    result = storage.save_tokens(test_tokens)
    assert result is False


def test_save_tokens_file_success(test_tokens, mock_config_dir, mock_fernet, mocker):
    """Test saving tokens using encrypted file backend."""
    storage = TokenStorage()
    storage.use_keyring = False

    test_key = Fernet.generate_key()
    mock_path = mocker.Mock()
    mock_path.parent = mocker.Mock()

    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_config_dir",
        return_value=mock_config_dir,
    )
    mocker.patch("cryptography.fernet.Fernet.generate_key", return_value=test_key)
    mocker.patch("cryptography.fernet.Fernet.encrypt", mock_fernet.encrypt)
    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_token_path",
        return_value=mock_path,
    )
    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_or_create_encryption_key",
        return_value=test_key,
    )

    result = storage.save_tokens(test_tokens)
    assert result is True
    mock_path.write_bytes.assert_called_once_with(b"encrypted_data")
    mock_path.chmod.assert_called_once_with(0o600)


def test_get_tokens_keyring_success(test_tokens, mocker):
    """Test retrieving tokens using keyring backend."""
    storage = TokenStorage()
    storage.use_keyring = True

    def mock_get_password(service, key):
        return test_tokens.get(key)

    mocker.patch("keyring.get_password", side_effect=mock_get_password)
    result = storage.get_tokens()
    assert result == test_tokens


def test_get_tokens_keyring_empty(mocker):
    """Test retrieving tokens using keyring backend when no tokens exist."""
    storage = TokenStorage(force_fernet=False)  # Force keyring usage
    storage.use_keyring = True  # Ensure keyring is used

    mocker.patch("keyring.get_password", return_value=None)
    result = storage.get_tokens()
    assert result is None


def test_get_tokens_file_success(test_tokens, mock_config_dir, caplog, mocker):
    """Test retrieving tokens using encrypted file backend."""
    caplog.set_level(logging.DEBUG)

    storage = TokenStorage()
    storage.use_keyring = False

    # Create a real Fernet instance for generating valid encrypted data.
    test_key = Fernet.generate_key()
    real_fernet = Fernet(test_key)
    # Encrypt the test tokens to produce a valid Fernet token.
    encrypted_data = real_fernet.encrypt(json.dumps(test_tokens).encode("utf-8"))

    # Create a mock path that simulates the token file.
    mock_path = mocker.Mock()
    mock_path.exists.return_value = True
    mock_path.read_bytes.return_value = encrypted_data

    # Create a mock Fernet instance that simulates decryption.
    mock_fernet = mocker.Mock()
    # When decrypt is called with the encrypted token, return the original token data.
    mock_fernet.decrypt.return_value = json.dumps(test_tokens).encode("utf-8")

    # Patch methods in TokenStorage to return our controlled values.
    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_config_dir",
        return_value=mock_config_dir,
    )
    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_or_create_encryption_key",
        return_value=test_key,
    )
    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_token_path",
        return_value=mock_path,
    )

    # IMPORTANT: Patch Fernet where it's used in your module.
    fernet_patch = mocker.patch(
        "nova_pydrobox.auth.token_storage.Fernet", return_value=mock_fernet
    )
    # If your code calls generate_key on Fernet, ensure it returns our test key.
    fernet_patch.generate_key.return_value = test_key

    # Execute the code under test.
    result = storage.get_tokens()

    # Print debug info (optional)
    print("\nTest Data Details:")
    print(f"Encrypted Data: {encrypted_data[:30]}...")
    print(f"Expected Tokens: {test_tokens}")
    print(f"Result: {result}")

    # Verify that the decrypt method was called with the encrypted data.
    mock_fernet.decrypt.assert_called_once_with(encrypted_data)
    # Assert that the tokens returned match the expected tokens.
    assert result == test_tokens


def test_get_tokens_file_not_found(mock_config_dir, mocker):
    """Test retrieving tokens using encrypted file backend when file doesn't exist."""
    storage = TokenStorage()
    storage.use_keyring = False

    mocker.patch("pathlib.Path.exists", return_value=False)
    result = storage.get_tokens()
    assert result is None


def test_clear_tokens_keyring_success(mocker):
    """Test clearing tokens using keyring backend."""
    storage = TokenStorage()
    storage.use_keyring = True

    mock_delete = mocker.patch("keyring.delete_password")
    result = storage.clear_tokens()
    assert result is True
    assert mock_delete.call_count == 4  # Four token types


def test_clear_tokens_file_success(mock_config_dir, mocker):
    """Test clearing tokens using encrypted file backend."""
    storage = TokenStorage()
    storage.use_keyring = False

    mock_path = mocker.patch.object(storage, "_get_token_path")
    fake_path = mocker.Mock()
    fake_path.exists.return_value = True
    mock_path.return_value = fake_path

    result = storage.clear_tokens()
    fake_path.unlink.assert_called_once()
    assert result is True


def test_clear_tokens_file_not_found(mock_config_dir, mocker):
    """Test clearing tokens using encrypted file backend when file doesn't exist."""
    storage = TokenStorage()
    storage.use_keyring = False

    mocker.patch.object(TokenStorage, "_get_config_dir", return_value=mock_config_dir)
    mocker.patch.object(Path, "exists", return_value=False)
    result = storage.clear_tokens()
    assert result is True  # Should return True even if no file exists


def test_get_config_dir_creation(mock_config_dir, mocker):
    """Test config directory creation."""
    storage = TokenStorage()

    # Use the mock_mkdir variable in an assertion
    mock_mkdir = mocker.patch("pathlib.Path.mkdir")
    config_dir = storage._get_config_dir()
    assert config_dir == mock_config_dir
    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
    assert mock_mkdir.call_count == 1  # Add assertion to use mock_mkdir


def test_get_config_dir_creation_error(mock_config_dir, mocker, caplog):
    """Test error handling in config directory creation."""
    caplog.set_level(logging.DEBUG)
    storage = TokenStorage()

    # Mock mkdir to raise OSError and store the mock for verification
    mock_mkdir = mocker.patch.object(
        Path, "mkdir", side_effect=OSError("Permission denied")
    )

    # Execute the code that should generate logs
    config_dir = storage._get_config_dir()

    # Verify expected behavior
    assert "Could not create config directory: Permission denied" in caplog.text
    assert config_dir == mock_config_dir
    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


def test_write_token(mocker):
    m = mocker.mock_open()
    mocker.patch("builtins.open", m)
    with open("dummy.txt", "w") as f:
        f.write("sample data")
    m.assert_called_once_with("dummy.txt", "w")
    m().write.assert_called_once_with("sample data")


def test_chmod_called(mock_config_dir, mocker):
    """Test that write_bytes is used to write data and chmod is called with expected permission when creating an encryption key."""
    storage = TokenStorage()

    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_config_dir",
        return_value=mock_config_dir,
    )
    mocker.patch.object(Path, "exists", return_value=False)
    mock_write = mocker.patch.object(Path, "write_bytes")
    mock_chmod = mocker.patch.object(Path, "chmod")
    mocker.patch.object(Path, "mkdir")

    generated_key = storage._get_or_create_encryption_key()
    mock_write.assert_called_once_with(generated_key)
    mock_chmod.assert_called_once_with(0o600)


def test_get_or_create_encryption_key_error(mock_config_dir, mocker):
    """Test error handling in _get_or_create_encryption_key."""
    storage = TokenStorage()

    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_config_dir",
        return_value=mock_config_dir,
    )
    mocker.patch.object(Path, "exists", return_value=True)
    mocker.patch.object(
        Path, "read_bytes", side_effect=PermissionError("Access denied")
    )

    with pytest.raises(PermissionError) as exc_info:
        storage._get_or_create_encryption_key()
    assert "Access denied" in str(exc_info.value)


def test_get_tokens_file_decrypt_error(mock_config_dir, mocker):
    """Test error handling in get_tokens for file backend decryption error."""
    storage = TokenStorage()
    storage.use_keyring = False

    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_config_dir",
        return_value=mock_config_dir,
    )
    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch("pathlib.Path.read_bytes", return_value=b"invalid_encrypted_data")
    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_or_create_encryption_key",
        return_value=Fernet.generate_key(),
    )

    result = storage.get_tokens()
    assert result is None


def test_get_tokens_keyring_partial(mocker):
    """Test get_tokens with keyring when not all required tokens are present."""
    storage = TokenStorage(force_fernet=False)  # Force keyring usage
    storage.use_keyring = True  # Ensure keyring is used

    def mock_get_password(service, key):
        # Only return some of the required tokens
        tokens = {
            "app_key": "test_key",
            "app_secret": "test_secret",
            # Missing access_token and refresh_token
        }
        return tokens.get(key)

    mocker.patch("keyring.get_password", side_effect=mock_get_password)
    result = storage.get_tokens()
    assert result is None


def test_test_keyring_error(mocker):
    """Test error handling in _test_keyring."""
    storage = TokenStorage()

    mocker.patch("keyring.set_password", side_effect=RuntimeError("Keyring error"))
    result = storage._test_keyring()
    assert result is False


def test_encode_decode_value():
    """Test the encoding and decoding of values."""
    storage = TokenStorage()
    test_value = "test@value!123"
    encoded = storage._encode_value(test_value)
    decoded = storage._decode_value(encoded)
    assert decoded == test_value
    assert encoded != test_value  # Ensure encoding actually changed the value


def test_encode_decode_special_characters():
    """Test encoding/decoding with special characters."""
    storage = TokenStorage()
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?/~`"
    encoded = storage._encode_value(special_chars)
    decoded = storage._decode_value(encoded)
    assert decoded == special_chars


def test_encode_value_error_handling(mocker):
    """Test error handling in encode_value."""
    storage = TokenStorage()
    mocker.patch("base64.b64encode", side_effect=Exception("Encoding error"))
    result = storage._encode_value("test")
    assert result == "test"  # Should return original value on error


def test_decode_value_error_handling(mocker):
    """Test error handling in decode_value."""
    storage = TokenStorage()
    mocker.patch("base64.b64decode", side_effect=Exception("Decoding error"))
    result = storage._decode_value("test")
    assert result == "test"  # Should return original value on error


def test_save_tokens_keyring_with_encoding(test_tokens, mocker):
    """Test that tokens are properly encoded when saved to keyring."""
    storage = TokenStorage(force_fernet=False)  # Force keyring usage
    storage.use_keyring = True  # Ensure keyring is used

    saved_values = {}

    def mock_set_password(service, key, value):
        saved_values[key] = value

    mocker.patch("keyring.set_password", side_effect=mock_set_password)
    storage.save_tokens(test_tokens)

    # Verify each value was encoded
    for key, value in test_tokens.items():
        encoded_value = storage._encode_value(value)
        assert saved_values[key] == encoded_value
        assert saved_values[key] != value  # Ensure encoding happened


def test_get_tokens_keyring_with_decoding(test_tokens, mocker):
    """Test that tokens are properly decoded when retrieved from keyring."""
    storage = TokenStorage()
    storage.use_keyring = True

    def mock_get_password(service, key):
        # Return encoded values
        value = test_tokens.get(key)
        return storage._encode_value(value) if value else None

    mocker.patch("keyring.get_password", side_effect=mock_get_password)
    result = storage.get_tokens()
    assert result == test_tokens  # Should match original tokens after decoding


def test_windows_always_uses_fernet(mocker):
    """Test that Windows platform always uses Fernet regardless of keyring availability."""
    mocker.patch("platform.system", return_value="Windows")
    storage = TokenStorage()
    assert storage.use_keyring is False


def test_fernet_fallback_on_keyring_failure(mocker):
    """Test fallback to Fernet when keyring fails."""
    storage = TokenStorage()
    storage.use_keyring = True

    mocker.patch("keyring.set_password", side_effect=Exception("Keyring failed"))
    mock_fernet = mocker.patch.object(storage, "_fernet_save_tokens", return_value=True)
    result = storage.save_tokens({"test": "value"})
    assert result is True
    mock_fernet.assert_called_once()


def test_fernet_save_tokens_windows(test_tokens, mock_config_dir, mocker):
    """Test saving tokens using Fernet on Windows platform."""
    # Force Windows behavior
    mocker.patch("platform.system", return_value="Windows")
    storage = TokenStorage()
    assert storage.use_keyring is False

    # Obtain a valid Fernet key
    test_key = Fernet.generate_key()

    # Create a mock Fernet instance whose encrypt method returns our expected encrypted data.
    mock_fernet = mocker.Mock()
    mock_fernet.encrypt.return_value = b"encrypted_data"

    # IMPORTANT: Patch Fernet in the namespace where it is used in your module.
    # This ensures that when TokenStorage calls Fernet(key), it gets our mock.
    fernet_patch = mocker.patch(
        "nova_pydrobox.auth.token_storage.Fernet", return_value=mock_fernet
    )
    # If generate_key is called via this patched reference, return our valid key.
    fernet_patch.generate_key.return_value = test_key

    # Patch helper methods so that save_tokens uses our controlled values.
    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_config_dir",
        return_value=mock_config_dir,
    )
    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_or_create_encryption_key",
        return_value=test_key,
    )
    # Simulate that the token file does not exist so that save_tokens proceeds to write it.
    mock_path = mocker.Mock()
    mock_path.exists.return_value = False
    # Ensure our mock token path has its own write_bytes and chmod methods we can assert on.
    mock_path.write_bytes = mocker.Mock()
    mock_path.chmod = mocker.Mock()
    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_token_path",
        return_value=mock_path,
    )

    # Call save_tokens – inside save_tokens, the patched Fernet is used so that:
    #   f = Fernet(test_key) returns our mock_fernet whose encrypt returns b"encrypted_data".
    result = storage.save_tokens(test_tokens)

    # Assert that saving tokens was successful and that the file was written with the expected data.
    assert result is True
    mock_path.write_bytes.assert_called_once_with(b"encrypted_data")
    mock_path.chmod.assert_called_once_with(0o600)


def test_fernet_get_tokens_windows(test_tokens, mock_config_dir, mocker):
    # Patch platform.system so Windows branch is taken
    mocker.patch("platform.system", return_value="Windows")
    storage = TokenStorage()
    assert storage.use_keyring is False

    # Use a valid Fernet key
    test_key = Fernet.generate_key()
    mock_encrypted_data = b"encrypted_data"

    mock_path = mocker.Mock()
    mock_path.exists.return_value = True
    mock_path.read_bytes.return_value = mock_encrypted_data

    # Create a simple mock Fernet instance with desired behavior
    mock_fernet = mocker.Mock()
    mock_fernet.decrypt.return_value = json.dumps(test_tokens).encode("utf-8")

    # Patch Fernet in the module where it's used
    mock_fernet_class = mocker.patch(
        "nova_pydrobox.auth.token_storage.Fernet", return_value=mock_fernet
    )
    # Optionally, if your code calls generate_key on Fernet, patch it too:
    mock_fernet_class.generate_key.return_value = test_key

    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_config_dir",
        return_value=mock_config_dir,
    )
    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_or_create_encryption_key",
        return_value=test_key,
    )
    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_token_path",
        return_value=mock_path,
    )

    result = storage.get_tokens()

    print("\nWindows Test Details:")
    print(f"Mock Encrypted Data: {mock_encrypted_data}")
    print(f"Mock Fernet Decrypt Called: {mock_fernet.decrypt.called}")
    print(f"Expected Tokens: {test_tokens}")
    print(f"Result: {result}")

    # Now the decrypt method should have been called with the expected data
    mock_fernet.decrypt.assert_called_once_with(mock_encrypted_data)
    assert result == test_tokens


def test_save_tokens_general_exception(test_tokens, mocker):
    """Test error handling in save_tokens for general exceptions."""
    storage = TokenStorage()
    storage.use_keyring = True

    # Mock keyring to raise a general exception
    mocker.patch("keyring.set_password", side_effect=Exception("Unexpected error"))
    # Mock _fernet_save_tokens to also fail
    mocker.patch.object(storage, "_fernet_save_tokens", return_value=False)

    result = storage.save_tokens(test_tokens)
    assert result is False


def test_get_tokens_general_exception(mocker):
    """Test error handling in get_tokens for general exceptions."""
    storage = TokenStorage(force_fernet=False)  # Force keyring usage
    storage.use_keyring = True  # Ensure keyring is used

    mocker.patch("keyring.get_password", side_effect=Exception("Unexpected error"))
    result = storage.get_tokens()
    assert result is None


def test_fernet_save_tokens_file_error(test_tokens, mock_config_dir, mocker):
    """Test error handling in _fernet_save_tokens for file operations."""
    storage = TokenStorage()
    storage.use_keyring = False

    test_key = Fernet.generate_key()
    mock_path = mocker.Mock()
    mock_path.write_bytes = mocker.Mock(side_effect=OSError("File write error"))

    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_config_dir",
        return_value=mock_config_dir,
    )
    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_or_create_encryption_key",
        return_value=test_key,
    )
    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_token_path",
        return_value=mock_path,
    )

    result = storage.save_tokens(test_tokens)
    assert result is False


def test_fernet_get_tokens_read_error(mock_config_dir, mocker):
    """Test error handling in _fernet_get_tokens for file read operations."""
    storage = TokenStorage()
    storage.use_keyring = False

    mock_path = mocker.Mock()
    mock_path.exists.return_value = True
    mock_path.read_bytes = mocker.Mock(side_effect=OSError("File read error"))

    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_config_dir",
        return_value=mock_config_dir,
    )
    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_token_path",
        return_value=mock_path,
    )

    result = storage.get_tokens()
    assert result is None


def test_clear_tokens_unlink_error(mock_config_dir, mocker):
    """Test error handling in clear_tokens for file deletion errors."""
    storage = TokenStorage()
    storage.use_keyring = False

    mock_path = mocker.Mock()
    mock_path.exists.return_value = True
    mock_path.unlink = mocker.Mock(side_effect=OSError("File deletion error"))

    mocker.patch(
        "nova_pydrobox.auth.token_storage.TokenStorage._get_token_path",
        return_value=mock_path,
    )

    result = storage.clear_tokens()
    assert result is False
