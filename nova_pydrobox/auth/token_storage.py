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

    def save_tokens(self, tokens: dict) -> bool:
        """Save tokens using available backend"""
        try:
            if self.use_keyring:
                for key, value in tokens.items():
                    keyring.set_password(self.service_name, key, value)
            else:
                from cryptography.fernet import Fernet

                key = self._get_or_create_encryption_key()
                f = Fernet(key)
                encrypted_data = f.encrypt(json.dumps(tokens).encode())
                self._fallback_path().write_bytes(encrypted_data)
            logger.info("Tokens saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving tokens: {e}")
            return False

    def get_tokens(self) -> Optional[dict]:
        """Retrieve tokens from available backend"""
        try:
            if self.use_keyring:
                tokens = {}
                for key in ["app_key", "app_secret", "access_token", "refresh_token"]:
                    value = keyring.get_password(self.service_name, key)
                    if value:
                        tokens[key] = value
                # Ensure all required tokens are present
                required_keys = ["app_key", "app_secret", "access_token", "refresh_token"]
                if all(key in tokens for key in required_keys):
                    return tokens
                else:
                    return None
            else:
                if not self._fallback_path().exists():
                    return None
                from cryptography.fernet import Fernet

                key = self._get_or_create_encryption_key()
                f = Fernet(key)
                encrypted_data = self._fallback_path().read_bytes()
                decrypted_data = f.decrypt(encrypted_data)
                return json.loads(decrypted_data)
        except Exception as e:
            logger.error(f"Error retrieving tokens: {e}")
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
