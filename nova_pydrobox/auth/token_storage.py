import base64
import json
import logging
from pathlib import Path
from typing import Optional

import keyring

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TokenStorage:
    def __init__(self, service_name: str = "nova-pydropbox"):
        self.service_name = service_name
        self.use_keyring = self._test_keyring()
        logger.info(
            f"Using {'keyring' if self.use_keyring else 'encrypted file'} backend for token storage"
        )

    def _test_keyring(self) -> bool:
        """Test if keyring is working"""
        try:
            keyring.set_password(self.service_name, "test", "test")
            test_value = keyring.get_password(self.service_name, "test")
            keyring.delete_password(self.service_name, "test")
            return test_value == "test"
        except Exception as e:
            logger.warning(f"Keyring not available: {e}")
            return False

    def _get_config_dir(self) -> Path:
        """Get configuration directory path"""
        config_dir = Path.home() / ".config" / "nova-pydropbox"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    def _fallback_path(self) -> Path:
        """Get path for fallback encrypted file storage"""
        return self._get_config_dir() / ".tokens.encrypted"

    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for fallback storage"""
        key_path = self._get_config_dir() / ".key"
        try:
            if key_path.exists():
                return key_path.read_bytes()
            else:
                from cryptography.fernet import Fernet

                key = Fernet.generate_key()
                key_path.write_bytes(key)
                key_path.chmod(0o600)  # Secure file permissions
                return key
        except Exception as e:
            logger.error(f"Error handling encryption key: {e}")
            raise

    def _encode_value(self, value: str) -> str:
        """Encode value to make it compatible with Windows Credential Manager"""
        try:
            # Convert to base64 to ensure Windows credential manager compatibility
            return base64.b64encode(value.encode()).decode()
        except Exception as e:
            logger.debug(f"Encoding failed: {e}")
            return value

    def _decode_value(self, value: str) -> str:
        """Decode value from Windows Credential Manager format"""
        try:
            return base64.b64decode(value.encode()).decode()
        except Exception as e:
            logger.debug(f"Decoding failed: {e}")
            return value

    def save_tokens(self, tokens: dict) -> bool:
        """Save tokens using available backend"""
        try:
            if self.use_keyring:
                for key, value in tokens.items():
                    # Encode values before storing
                    encoded_value = self._encode_value(value)
                    try:
                        keyring.set_password(self.service_name, key, encoded_value)
                    except Exception as e:
                        logger.error(f"Failed to save {key}: {e}")
                        return self._fallback_save_tokens(tokens)
            else:
                return self._fallback_save_tokens(tokens)
            logger.info("Tokens saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving tokens: {e}")
            return self._fallback_save_tokens(tokens)

    def get_tokens(self) -> Optional[dict]:
        """Retrieve tokens from available backend"""
        try:
            if self.use_keyring:
                tokens = {}
                for key in ["app_key", "app_secret", "access_token", "refresh_token"]:
                    try:
                        value = keyring.get_password(self.service_name, key)
                        if value:
                            # Decode values after retrieving
                            tokens[key] = self._decode_value(value)
                    except Exception as e:
                        logger.error(f"Failed to retrieve {key}: {e}")
                        return self._fallback_get_tokens()

                required_keys = [
                    "app_key",
                    "app_secret",
                    "access_token",
                    "refresh_token",
                ]
                if all(key in tokens for key in required_keys):
                    return tokens
                return None
            else:
                return self._fallback_get_tokens()
        except Exception as e:
            logger.error(f"Error retrieving tokens: {e}")
            return self._fallback_get_tokens()

    def _fallback_save_tokens(self, tokens: dict) -> bool:
        """Fallback to file-based storage"""
        try:
            from cryptography.fernet import Fernet

            key = self._get_or_create_encryption_key()
            f = Fernet(key)
            encrypted_data = f.encrypt(json.dumps(tokens).encode())
            self._fallback_path().write_bytes(encrypted_data)
            return True
        except Exception as e:
            logger.error(f"Fallback save failed: {e}")
            return False

    def _fallback_get_tokens(self) -> Optional[dict]:
        """Fallback to file-based storage for retrieval"""
        try:
            if not self._fallback_path().exists():
                return None
            from cryptography.fernet import Fernet

            key = self._get_or_create_encryption_key()
            f = Fernet(key)
            encrypted_data = self._fallback_path().read_bytes()
            decrypted_data = f.decrypt(encrypted_data)
            return json.loads(decrypted_data)
        except Exception as e:
            logger.error(f"Fallback retrieval failed: {e}")
            return None

    def clear_tokens(self) -> bool:
        """Clear all stored tokens"""
        try:
            if self.use_keyring:
                for key in ["app_key", "app_secret", "access_token", "refresh_token"]:
                    try:
                        keyring.delete_password(self.service_name, key)
                    except keyring.errors.PasswordDeleteError:
                        pass
            else:
                if self._fallback_path().exists():
                    self._fallback_path().unlink()
            logger.info("Tokens cleared successfully")
            return True
        except Exception as e:
            logger.error(f"Error clearing tokens: {e}")
            return False
