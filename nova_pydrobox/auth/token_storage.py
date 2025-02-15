import base64
import json
import logging
import platform
from pathlib import Path
from typing import Optional

import keyring
from cryptography.fernet import Fernet, InvalidToken

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TokenStorage:
    """
    A class to handle secure storage of Dropbox API tokens.

    This class provides two storage backends:
    1. System keyring (default on non-Windows systems)
    2. File-based storage with Fernet encryption (default on Windows)

    Attributes:
        service_name (str): Name of the service for keyring storage
        use_keyring (bool): Whether to use keyring backend or Fernet encryption

    Args:
        service_name (str, optional): Service name for keyring storage. Defaults to "nova-pydrobox".
        force_fernet (bool, optional): Force use of Fernet encryption instead of keyring. Defaults to None.
    """

    def __init__(self, service_name: str = "nova-pydrobox", force_fernet: bool = None):
        self.service_name = service_name
        # Allow force_fernet to override platform check for testing
        if force_fernet is not None:
            self.use_keyring = not force_fernet
        else:
            # Default behavior: Force Fernet encryption on Windows
            self.use_keyring = platform.system() != "Windows" and self._test_keyring()

        logger.info(
            f"Using {'keyring' if self.use_keyring else 'Fernet encryption'} backend for token storage"
        )

    def _test_keyring(self) -> bool:
        """
        Test if the system keyring is working correctly.

        Returns:
            bool: True if keyring is working, False otherwise
        """
        try:
            keyring.set_password(self.service_name, "test", "test")
            test_value = keyring.get_password(self.service_name, "test")
            keyring.delete_password(self.service_name, "test")
            return test_value == "test"
        except Exception as e:
            logger.warning(f"Keyring not available: {e}")
            return False

    def _get_config_dir(self) -> Path:
        """
        Get or create the configuration directory path.

        Returns:
            Path: Path to the configuration directory

        Note:
            Creates directory if it doesn't exist
        """
        config_dir = Path.home() / ".config" / "nova-pydropbox"
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning(f"Could not create config directory: {e}")
        return config_dir

    def _get_or_create_encryption_key(self) -> bytes:
        """
        Get existing or create new encryption key for Fernet.

        Returns:
            bytes: The encryption key

        Raises:
            Exception: If key creation or retrieval fails
        """
        key_path = self._get_config_dir() / ".key"
        try:
            if key_path.exists():
                return key_path.read_bytes()
            else:
                # Create config directory if it doesn't exist
                key_path.parent.mkdir(parents=True, exist_ok=True)
                key = Fernet.generate_key()
                key_path.write_bytes(key)
                key_path.chmod(0o600)  # Secure file permissions
                return key
        except Exception as e:
            logger.error(f"Error handling encryption key: {e}")
            raise

    def _encode_value(self, value: str) -> str:
        """
        Encode a string value using base64.

        Args:
            value (str): String to encode

        Returns:
            str: Base64 encoded string

        Note:
            Falls back to original value if encoding fails
        """
        try:
            return base64.b64encode(value.encode()).decode()
        except Exception as e:
            logger.error(f"Error encoding value: {e}")
            return value

    def _decode_value(self, value: str) -> str:
        """
        Decode a base64 encoded string.

        Args:
            value (str): Base64 encoded string to decode

        Returns:
            str: Decoded string

        Note:
            Falls back to original value if decoding fails
        """
        try:
            return base64.b64decode(value.encode()).decode()
        except Exception as e:
            logger.error(f"Error decoding value: {e}")
            return value

    def save_tokens(self, tokens: dict) -> bool:
        """
        Save tokens using the configured storage backend.

        Args:
            tokens (dict): Dictionary containing token key-value pairs

        Returns:
            bool: True if save successful, False otherwise

        Note:
            Falls back to Fernet encryption if keyring save fails
        """
        try:
            # Use Fernet if forced or on Windows
            if not self.use_keyring:
                return self._fernet_save_tokens(tokens)

            # Use keyring if available
            failed_keys = []
            for key, value in tokens.items():
                try:
                    encoded_value = self._encode_value(value)
                    keyring.set_password(self.service_name, key, encoded_value)
                except Exception as e:
                    logger.error(f"Failed to save {key}: {e}")
                    failed_keys.append(key)

            if failed_keys:
                logger.info("Falling back to Fernet encryption for all tokens")
                return self._fernet_save_tokens(tokens)

            logger.info("Tokens saved successfully using keyring")
            return True
        except Exception as e:
            logger.error(f"Error saving tokens: {e}")
            return False

    def get_tokens(self) -> Optional[dict]:
        """
        Retrieve tokens from the configured storage backend.

        Returns:
            Optional[dict]: Dictionary containing tokens if successful, None otherwise

        Required token keys:
            - app_key
            - app_secret
            - access_token
            - refresh_token
        """
        try:
            # Use Fernet if forced or on Windows
            if not self.use_keyring:
                return self._fernet_get_tokens()

            # Use keyring if available
            tokens = {}
            for key in ["app_key", "app_secret", "access_token", "refresh_token"]:
                encoded_value = keyring.get_password(self.service_name, key)
                if encoded_value:
                    tokens[key] = self._decode_value(encoded_value)

            if all(
                key in tokens
                for key in ["app_key", "app_secret", "access_token", "refresh_token"]
            ):
                return tokens
            return None
        except Exception as e:
            logger.error(f"Error retrieving tokens: {e}")
            return None

    def _fernet_save_tokens(self, tokens: dict) -> bool:
        """
        Save tokens using Fernet encryption to a file.

        Args:
            tokens (dict): Dictionary containing token key-value pairs

        Returns:
            bool: True if save successful, False otherwise

        Note:
            Encrypts tokens and saves to .tokens.encrypted file
        """
        try:
            key = self._get_or_create_encryption_key()
            f = Fernet(key)
            token_data = json.dumps(tokens).encode()
            encrypted_data = f.encrypt(token_data)
            token_path = self._get_token_path()
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_bytes(encrypted_data)
            token_path.chmod(0o600)  # Secure file permissions
            logger.info("Tokens saved successfully using Fernet encryption")
            return True
        except Exception as e:
            logger.error(f"Fernet save failed: {e}")
            return False

    def _fernet_get_tokens(self) -> Optional[dict]:
        """
        Retrieve tokens using Fernet decryption from file.

        Returns:
            Optional[dict]: Dictionary containing tokens if successful, None otherwise

        Note:
            Validates presence of all required token keys after decryption
        """
        try:
            logger.debug("Starting _fernet_get_tokens")
            token_path = self._get_token_path()
            logger.debug(f"Token path: {token_path}")

            if not token_path.exists():
                logger.debug("Token file does not exist")
                return None

            key = self._get_or_create_encryption_key()
            logger.debug(f"Got encryption key: {key[:10]}...")

            f = Fernet(key)
            logger.debug("Created Fernet instance")

            encrypted_data = token_path.read_bytes()
            logger.debug(f"Read encrypted data: {encrypted_data[:20]}...")

            try:
                logger.debug("Attempting to decrypt data")
                decrypted_data = f.decrypt(encrypted_data)
                logger.debug(f"Decrypted data: {decrypted_data[:50]}...")

                tokens = json.loads(decrypted_data.decode("utf-8"))
                logger.debug(f"Parsed tokens: {tokens}")

                required_keys = {
                    "app_key",
                    "app_secret",
                    "access_token",
                    "refresh_token",
                }
                logger.debug(f"Checking required keys: {required_keys}")

                if not all(key in tokens for key in required_keys):
                    logger.error("Missing required tokens in decrypted data")
                    return None

                logger.debug("Tokens retrieved successfully")
                return tokens

            except InvalidToken:
                logger.error("Failed to decrypt token data - invalid token")
                return None
            except json.JSONDecodeError:
                logger.error("Failed to parse decrypted token data")
                return None

        except Exception as e:
            logger.error(f"Fernet retrieval failed: {str(e)}")
            logger.exception("Full traceback:")  # This will log the full traceback
            return None

    def _get_token_path(self) -> Path:
        """
        Get path for encrypted token storage file.

        Returns:
            Path: Path to the encrypted tokens file
        """
        return self._get_config_dir() / ".tokens.encrypted"

    def clear_tokens(self) -> bool:
        """
        Clear all stored tokens from the active backend.

        Returns:
            bool: True if clearing successful, False otherwise

        Note:
            Handles both keyring and file-based storage
        """
        try:
            if self.use_keyring:
                for key in ["app_key", "app_secret", "access_token", "refresh_token"]:
                    try:
                        keyring.delete_password(self.service_name, key)
                    except keyring.errors.PasswordDeleteError:
                        pass
            else:
                token_path = self._get_token_path()
                if token_path.exists():
                    try:
                        token_path.unlink()
                    except OSError as e:
                        logger.error(f"Failed to delete token file: {e}")
                        return False
            logger.info("Tokens cleared successfully")
            return True
        except Exception as e:
            logger.error(f"Error clearing tokens: {e}")
            return False
