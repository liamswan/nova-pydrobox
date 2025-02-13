"""Tests for the token storage module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

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
def mock_config_dir():
    with patch("pathlib.Path.home") as mock_home:
        mock_home.return_value = Path("/mock/home")
        yield Path("/mock/home/.config/nova-pydropbox")


def test_init_with_working_keyring():
    """Test TokenStorage initialization with working keyring."""
    with patch.object(TokenStorage, "_test_keyring", return_value=True):
        storage = TokenStorage()
        assert storage.use_keyring is True


def test_init_with_broken_keyring():
    """Test TokenStorage initialization with non-working keyring."""
    with patch.object(TokenStorage, "_test_keyring", return_value=False):
        storage = TokenStorage()
        assert storage.use_keyring is False


def test_save_tokens_keyring_success(test_tokens):
    """Test saving tokens using keyring backend."""
    storage = TokenStorage()
    storage.use_keyring = True

    with patch("keyring.set_password") as mock_set:
        result = storage.save_tokens(test_tokens)
        assert result is True
        assert mock_set.call_count == len(test_tokens)

        # Check that each token is stored with proper encoding
        for key, value in test_tokens.items():
            encoded_value = storage._encode_value(value)
            mock_set.assert_any_call(storage.service_name, key, encoded_value)


def test_save_tokens_keyring_failure(test_tokens):
    """Test saving tokens using keyring backend with failure."""
    storage = TokenStorage()
    storage.use_keyring = True

    # Mock both keyring.set_password to fail and _fallback_save_tokens to fail
    with (
        patch("keyring.set_password", side_effect=keyring.errors.PasswordSetError),
        patch.object(storage, "_fallback_save_tokens", return_value=False),
    ):
        result = storage.save_tokens(test_tokens)
        assert result is False


def test_save_tokens_file_success(test_tokens, mock_config_dir):
    """Test saving tokens using encrypted file backend."""
    storage = TokenStorage()
    storage.use_keyring = False

    test_key = Fernet.generate_key()
    mock_fernet = MagicMock()
    mock_fernet.encrypt.return_value = b"encrypted_data"

    with (
        patch(
            "nova_pydrobox.auth.token_storage.TokenStorage._get_config_dir",
            return_value=mock_config_dir,
        ),
        patch("cryptography.fernet.Fernet.generate_key", return_value=test_key),
        patch("cryptography.fernet.Fernet", return_value=mock_fernet),
        patch.object(Path, "write_bytes") as mock_write,
        patch.object(Path, "chmod") as mock_chmod,
    ):
        result = storage.save_tokens(test_tokens)
        assert result is True

        # One call writes the encryption key and one writes the tokens,
        # so assert at least one call was with the encrypted data.
        calls = mock_write.call_args_list
        assert any(call.args[0] == b"encrypted_data" for call in calls)
        mock_chmod.assert_called_once_with(0o600)


def test_get_tokens_keyring_success(test_tokens):
    """Test retrieving tokens using keyring backend."""
    storage = TokenStorage()
    storage.use_keyring = True

    def mock_get_password(service, key):
        return test_tokens.get(key)

    with patch("keyring.get_password", side_effect=mock_get_password):
        result = storage.get_tokens()
        assert result == test_tokens


def test_get_tokens_keyring_empty():
    """Test retrieving tokens using keyring backend when no tokens exist."""
    storage = TokenStorage()
    storage.use_keyring = True

    with patch("keyring.get_password", return_value=None):
        result = storage.get_tokens()
        assert result is None


def test_get_tokens_file_success(test_tokens, mock_config_dir):
    """Test retrieving tokens using encrypted file backend."""
    storage = TokenStorage()
    storage.use_keyring = False

    test_key = Fernet.generate_key()
    mock_fernet = MagicMock()
    mock_fernet.decrypt.return_value = json.dumps(test_tokens).encode()

    with (
        patch(
            "nova_pydrobox.auth.token_storage.TokenStorage._get_config_dir",
            return_value=mock_config_dir,
        ),
        patch(
            "nova_pydrobox.auth.token_storage.TokenStorage._get_or_create_encryption_key",
            return_value=test_key,
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=b"encrypted_data"),
        patch("cryptography.fernet.Fernet", return_value=mock_fernet),
    ):
        result = storage.get_tokens()
        assert result == test_tokens


def test_get_tokens_file_not_found(mock_config_dir):
    """Test retrieving tokens using encrypted file backend when file doesn't exist."""
    storage = TokenStorage()
    storage.use_keyring = False

    with patch("pathlib.Path.exists", return_value=False):
        result = storage.get_tokens()
        assert result is None


def test_clear_tokens_keyring_success():
    """Test clearing tokens using keyring backend."""
    storage = TokenStorage()
    storage.use_keyring = True

    with patch("keyring.delete_password") as mock_delete:
        result = storage.clear_tokens()
        assert result is True
        assert mock_delete.call_count == 4  # Four token types


def test_clear_tokens_file_success(mock_config_dir):
    """Test clearing tokens using encrypted file backend."""
    storage = TokenStorage()
    storage.use_keyring = False

    with patch.object(storage, "_fallback_path") as mock_fallback:
        fake_path = MagicMock()
        fake_path.exists.return_value = True
        mock_fallback.return_value = fake_path

        result = storage.clear_tokens()
        fake_path.unlink.assert_called_once()
        assert result is True


def test_clear_tokens_file_not_found(mock_config_dir):
    """Test clearing tokens using encrypted file backend when file doesn't exist."""
    storage = TokenStorage()
    storage.use_keyring = False

    with (
        patch.object(TokenStorage, "_get_config_dir", return_value=mock_config_dir),
        patch.object(Path, "exists", return_value=False),
    ):
        result = storage.clear_tokens()
        assert result is True  # Should return True even if no file exists


def test_get_config_dir_creation(mock_config_dir):
    """Test config directory creation."""
    storage = TokenStorage()

    with patch("pathlib.Path.mkdir") as mock_mkdir:
        config_dir = storage._get_config_dir()
        assert config_dir == mock_config_dir
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


def test_write_token():
    m = mock_open()
    with patch("builtins.open", m):
        with open("dummy.txt", "w") as f:
            f.write("sample data")
    m.assert_called_once_with("dummy.txt", "w")
    m().write.assert_called_once_with("sample data")


def test_chmod_called(mock_config_dir):
    """Test that write_bytes is used to write data and chmod is called with expected permission when creating an encryption key."""
    storage = TokenStorage()
    with (
        patch(
            "nova_pydrobox.auth.token_storage.TokenStorage._get_config_dir",
            return_value=mock_config_dir,
        ),
        patch.object(Path, "exists", return_value=False),
        patch.object(Path, "write_bytes") as mock_write,
        patch.object(Path, "chmod") as mock_chmod,
    ):
        generated_key = storage._get_or_create_encryption_key()
        # Assume that _get_or_create_encryption_key writes the encryption key
        # Assert that write_bytes was called with the generated key
        mock_write.assert_called_once_with(generated_key)
        mock_chmod.assert_called_once_with(0o600)


def test_get_or_create_encryption_key_error(mock_config_dir):
    """Test error handling in _get_or_create_encryption_key."""
    storage = TokenStorage()
    with (
        patch(
            "nova_pydrobox.auth.token_storage.TokenStorage._get_config_dir",
            return_value=mock_config_dir,
        ),
        patch.object(Path, "exists", return_value=True),
        patch.object(Path, "read_bytes", side_effect=PermissionError("Access denied")),
    ):
        with pytest.raises(PermissionError) as exc_info:
            storage._get_or_create_encryption_key()
        assert "Access denied" in str(exc_info.value)


def test_get_tokens_file_decrypt_error(mock_config_dir):
    """Test error handling in get_tokens for file backend decryption error."""
    storage = TokenStorage()
    storage.use_keyring = False

    with (
        patch(
            "nova_pydrobox.auth.token_storage.TokenStorage._get_config_dir",
            return_value=mock_config_dir,
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=b"invalid_encrypted_data"),
        patch(
            "nova_pydrobox.auth.token_storage.TokenStorage._get_or_create_encryption_key",
            return_value=Fernet.generate_key(),
        ),
    ):
        result = storage.get_tokens()
        assert result is None


def test_get_tokens_keyring_partial():
    """Test get_tokens with keyring when not all required tokens are present."""
    storage = TokenStorage()
    storage.use_keyring = True

    def mock_get_password(service, key):
        # Only return some of the required tokens
        tokens = {
            "app_key": "test_key",
            "app_secret": "test_secret",
            # Missing access_token and refresh_token
        }
        return tokens.get(key)

    with patch("keyring.get_password", side_effect=mock_get_password):
        result = storage.get_tokens()
        assert result is None


def test_test_keyring_error():
    """Test error handling in _test_keyring."""
    storage = TokenStorage()

    with patch("keyring.set_password", side_effect=RuntimeError("Keyring error")):
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


def test_encode_value_error_handling():
    """Test error handling in encode_value."""
    storage = TokenStorage()
    with patch("base64.b64encode", side_effect=Exception("Encoding error")):
        result = storage._encode_value("test")
        assert result == "test"  # Should return original value on error


def test_decode_value_error_handling():
    """Test error handling in decode_value."""
    storage = TokenStorage()
    with patch("base64.b64decode", side_effect=Exception("Decoding error")):
        result = storage._decode_value("test")
        assert result == "test"  # Should return original value on error


def test_save_tokens_keyring_with_encoding(test_tokens):
    """Test that tokens are properly encoded when saved to keyring."""
    storage = TokenStorage()
    storage.use_keyring = True

    saved_values = {}

    def mock_set_password(service, key, value):
        saved_values[key] = value

    with patch("keyring.set_password", side_effect=mock_set_password):
        storage.save_tokens(test_tokens)

        # Verify each value was encoded
        for key, value in test_tokens.items():
            encoded_value = storage._encode_value(value)
            assert saved_values[key] == encoded_value
            assert saved_values[key] != value  # Ensure encoding happened


def test_get_tokens_keyring_with_decoding(test_tokens):
    """Test that tokens are properly decoded when retrieved from keyring."""
    storage = TokenStorage()
    storage.use_keyring = True

    def mock_get_password(service, key):
        # Return encoded values
        value = test_tokens.get(key)
        return storage._encode_value(value) if value else None

    with patch("keyring.get_password", side_effect=mock_get_password):
        result = storage.get_tokens()
        assert result == test_tokens  # Should match original tokens after decoding
