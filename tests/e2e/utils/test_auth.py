"""E2E test authentication utilities."""
import logging
from typing import Optional

import dropbox

from nova_pydrobox.auth.authenticator import Authenticator
from nova_pydrobox.auth.token_storage import TokenStorage

logger = logging.getLogger(__name__)

class E2ETestAuthenticator(Authenticator):
    """Authenticator for E2E tests using pre-configured test credentials."""
    
    def __init__(self, test_app_key: str, test_app_secret: str, test_refresh_token: str):
        """
        Initialize E2E test authenticator with test credentials.
        
        Args:
            test_app_key: App key for test Dropbox app
            test_app_secret: App secret for test Dropbox app
            test_refresh_token: OAuth2 refresh token for test account
        """
        super().__init__()
        self.test_credentials = {
            "app_key": test_app_key,
            "app_secret": test_app_secret,
            "refresh_token": test_refresh_token,
            "access_token": None  # Will be obtained through refresh
        }

    def authenticate_dropbox(self, force_reauth: bool = False, force_fernet: bool = None) -> bool:
        """Override to use test credentials instead of interactive flow."""
        logger.info("Using pre-configured test credentials for E2E tests")
        try:
            # Initialize storage with force_fernet option
            self.storage = TokenStorage(force_fernet=force_fernet)
            return self.storage.save_tokens(self.test_credentials)
        except Exception as e:
            logger.error(f"Failed to authenticate with test credentials: {e}")
            return False

    def get_dropbox_client(self) -> Optional[dropbox.Dropbox]:
        """
        Create Dropbox client using test credentials.
        
        Returns:
            Optional[dropbox.Dropbox]: Authenticated client or None if failed
        """
        try:
            dbx = dropbox.Dropbox(
                oauth2_refresh_token=self.test_credentials["refresh_token"],
                app_key=self.test_credentials["app_key"],
                app_secret=self.test_credentials["app_secret"],
            )
            # Verify connection
            dbx.users_get_current_account()
            logger.info("Successfully connected to Dropbox with test credentials")
            return dbx
        except Exception as e:
            logger.error(f"Error connecting to Dropbox with test credentials: {e}")
            return None
