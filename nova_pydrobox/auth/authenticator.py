import logging
import time
import webbrowser
from functools import wraps
from typing import Optional

import dropbox

from nova_pydrobox.auth.token_storage import TokenStorage

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def rate_limit(max_attempts: int = 3, cooldown: int = 300):
    """Rate limiting decorator for authentication attempts."""

    def decorator(func):
        attempts = {}

        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            # Clear old attempts
            attempts.clear()

            if attempts.get(func.__name__, 0) >= max_attempts:
                last_attempt = attempts.get(f"{func.__name__}_last", 0)
                if now - last_attempt < cooldown:
                    wait_time = int(cooldown - (now - last_attempt))
                    print(
                        f"\nToo many authentication attempts. Please wait {wait_time} seconds."
                    )
                    return False
                attempts[func.__name__] = 0

            result = func(*args, **kwargs)
            if not result:
                attempts[func.__name__] = attempts.get(func.__name__, 0) + 1
                attempts[f"{func.__name__}_last"] = now
            return result

        return wrapper

    return decorator


class Authenticator:
    """
    Handles Dropbox authentication and client creation.

    This class manages the OAuth2 authentication flow for Dropbox, including:
    - Initial setup of app credentials
    - OAuth2 authorization flow
    - Token storage and retrieval
    - Client creation with automatic token refresh

    Attributes:
        storage (TokenStorage): Instance of TokenStorage for secure token management
    """

    def __init__(self):
        """Initialize authenticator with token storage."""
        self.storage = TokenStorage()

    def setup_credentials(self):
        """
        Guide user through setting up Dropbox API credentials.

        This method:
        1. Opens the Dropbox App Console in the default browser
        2. Guides the user through app creation
        3. Collects app key and secret

        Returns:
            tuple[str, str]: A tuple containing (app_key, app_secret)

        Note:
            Interactive process that requires user input
        """
        print("\n=== Dropbox API Credentials Setup Guide ===")
        print("\n1. I'll open the Dropbox App Console in your browser.")
        print("2. If you're not logged in, please log in to your Dropbox account.")
        print("3. Click 'Create app' if you haven't created one yet.")
        input("\nPress Enter to open the Dropbox App Console...")
        try:
            webbrowser.open("https://www.dropbox.com/developers/apps")
        except Exception as e:
            logger.warning(f"Failed to open browser: {e}")
            print("\nCouldn't open browser automatically.")
            print("Please manually visit: https://www.dropbox.com/developers/apps")

        print("\nIn the Dropbox App Console:")
        print("1. Choose 'Scoped access' for API access type")
        print("2. Choose 'Full Dropbox' or 'App folder' based on your needs")
        print("3. Give your app a unique name")
        input("\nPress Enter to continue after creating your app...")
        print("\nOnce created, in your app's settings:")
        print("1. Find the 'App key' and 'App secret' under the Settings tab")
        print("2. Enter them below\n")

        app_key = input("Enter your App key: ").strip()
        app_secret = input("Enter your App secret: ").strip()

        if not app_key or not app_secret:
            print("\nBoth App key and App secret are required!")
            app_key = input("Enter your App key: ").strip()
            app_secret = input("Enter your App secret: ").strip()

        if not app_key or not app_secret:
            logger.error(
                "App key and App secret are required but were not provided. Please ensure both fields are filled."
            )
            return None, None

        return app_key, app_secret

    @rate_limit()
    def authenticate_dropbox(
        self, force_reauth: bool = False, force_fernet: bool = None
    ) -> bool:
        """
        Perform OAuth2 authentication with Dropbox.

        Args:
            force_reauth (bool, optional): Force re-authentication even if tokens exist.
                                         Defaults to False.
            force_fernet (bool, optional): Force use of Fernet encryption instead of keyring.
                                         Defaults to None.

        Returns:
            bool: True if authentication successful, False otherwise

        Note:
            - Uses PKCE flow for enhanced security
            - Stores tokens using TokenStorage
            - Includes retry logic for token storage
        """
        # Initialize storage with force_fernet option
        self.storage = TokenStorage(force_fernet=force_fernet)

        if not force_reauth:
            existing_tokens = self.storage.get_tokens()
            if existing_tokens:
                print("Already authenticated. Skipping authentication process.")
                return True

        try:
            app_key, app_secret = self.setup_credentials()
            flow = dropbox.DropboxOAuth2FlowNoRedirect(
                consumer_key=app_key,
                consumer_secret=app_secret,
                token_access_type="offline",  # This ensures we get a refresh token
            )

            authorize_url = flow.start()
            print("\n1. I'll open the Dropbox authentication page in your browser.")
            print("2. Select an account. (you might have to log in first)")
            print("3. Click 'Allow'.")
            print("4. Copy the authorization code.")
            webbrowser.open(authorize_url)
            auth_code = input("\nEnter the authorization code here: ").strip()
            print("\nAuthenticating...")
            while True:
                try:
                    oauth_result = flow.finish(auth_code)
                    break
                except dropbox.exceptions.AuthError as e:
                    print(f"\nAuthentication failed: {e}")
                    auth_code = input(
                        "\nInvalid auth code. Please enter the authorization code again: "
                    ).strip()

            tokens = {
                "app_key": app_key,
                "app_secret": app_secret,
                "access_token": oauth_result.access_token,
                "refresh_token": oauth_result.refresh_token,
            }

            for attempt in range(2):  # Retry saving tokens up to 2 times
                print(f"DEBUG: Attempt {attempt + 1} to save tokens")
                if self.storage.save_tokens(tokens):
                    print("\nAuthentication successful! Tokens securely stored.")
                    return True
                else:
                    print("\nError saving tokens. Retrying...")
            print("\nError saving tokens after retrying.")
            return False
        except Exception as e:
            print(f"\nAuthentication failed: {e}")
            return False

    def get_dropbox_client(self):
        """
        Create an authenticated Dropbox client.

        Returns:
            Optional[dropbox.Dropbox]: Authenticated Dropbox client or None if failed

        Note:
            - Automatically handles token refresh
            - Validates connection by checking account access
            - Returns None if authentication fails
        """
        credentials = self.storage.get_tokens()
        if not credentials:
            logger.error("No credentials found")
            return None
        try:
            kwargs = {
                "oauth2_refresh_token": credentials["refresh_token"],
                "app_key": credentials["app_key"],
                "app_secret": credentials["app_secret"],
            }
            if credentials.get("access_token"):
                kwargs["oauth2_access_token"] = credentials["access_token"]

            dbx = dropbox.Dropbox(**kwargs)
            try:
                dbx.users_get_current_account()
            except dropbox.exceptions.AuthError as e:
                logger.warning(f"Auth error: {e}. Attempting to refresh token...")
                # Token refresh is handled automatically by the SDK
                try:
                    dbx.users_get_current_account()
                except dropbox.exceptions.AuthError:
                    logger.error("Token refresh failed")
                    return None
            logger.info("Successfully connected to Dropbox")
            return dbx
        except Exception as e:
            logger.error(f"Error connecting to Dropbox: {e}")
            return None


# Top-level aliases to support module-level imports
def authenticate_dropbox(*args, force_fernet: bool = None, **kwargs) -> bool:
    """
    Module-level function to authenticate with Dropbox.

    Args:
        *args: Variable length argument list
        force_fernet (bool, optional): Force use of Fernet encryption instead of keyring
        **kwargs: Arbitrary keyword arguments

    Returns:
        bool: True if authentication successful, False otherwise

    Example:
        ```python
        # Use keyring (default)
        success = authenticate_dropbox(force_reauth=True)

        # Force Fernet encryption
        success = authenticate_dropbox(force_reauth=True, force_fernet=True)
        ```
    """
    return Authenticator().authenticate_dropbox(
        *args, force_fernet=force_fernet, **kwargs
    )


def get_dropbox_client(*args, **kwargs) -> Optional[dropbox.Dropbox]:
    """
    Module-level function to get an authenticated Dropbox client.

    Args:
        *args: Variable length argument list
        **kwargs: Arbitrary keyword arguments

    Returns:
        Optional[dropbox.Dropbox]: Authenticated client or None if failed

    Example:
        ```python
        dbx = get_dropbox_client()
        if dbx:
            account = dbx.users_get_current_account()
        ```
    """
    return Authenticator().get_dropbox_client(*args, **kwargs)


def setup_credentials(*args, **kwargs) -> tuple[str, str]:
    """
    Module-level function to set up Dropbox credentials.

    Args:
        *args: Variable length argument list
        **kwargs: Arbitrary keyword arguments

    Returns:
        tuple[str, str]: A tuple containing (app_key, app_secret)

    Example:
        ```python
        app_key, app_secret = setup_credentials()
        ```
    """
    return Authenticator().setup_credentials(*args, **kwargs)


def main():
    """
    Command-line interface for authentication setup.

    Provides interactive flow for:
    - Checking existing credentials
    - Option to re-authenticate
    - Guiding through authentication process
    """
    print("Welcome to Nova-PyDropbox Authentication Setup!")
    auth = Authenticator()
    storage = auth.storage
    existing_tokens = storage.get_tokens()

    if existing_tokens:
        print("\nExisting credentials found!")
        choice = input("Would you like to re-authenticate? (y/N): ").lower()
        if choice == "y":
            print("Re-authenticating...")
            print("Please follow the prompts to re-authenticate your Dropbox account.")
            auth.authenticate_dropbox(force_reauth=True)
        else:
            print("Skipping re-authentication.")
            return
    else:
        auth.authenticate_dropbox()


if __name__ == "__main__":
    main()
