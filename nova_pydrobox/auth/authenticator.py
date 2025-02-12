import logging
import webbrowser

import dropbox

from nova_pydrobox.auth.token_storage import TokenStorage

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Authenticator:
    def __init__(self):
        self.storage = TokenStorage()

    def setup_credentials(self):
        print("\n=== Dropbox API Credentials Setup Guide ===")
        print("\n1. I'll open the Dropbox App Console in your browser.")
        print("2. If you're not logged in, please log in to your Dropbox account.")
        print("3. Click 'Create app' if you haven't created one yet.")
        input("\nPress Enter to open the Dropbox App Console...")
        webbrowser.open("https://www.dropbox.com/developers/apps")

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

        while not app_key or not app_secret:
            print("\nBoth App key and App secret are required!")
            app_key = input("Enter your App key: ").strip()
            app_secret = input("Enter your App secret: ").strip()

        return app_key, app_secret

    def authenticate_dropbox(self, force_reauth=False):
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
                token_access_type="offline",
                use_pkce=True,
            )

            authorize_url = flow.start()
            print("\n1. I'll open the Dropbox authentication page in your browser.")
            print("2. Select an account. (you might have to log in first)")
            print("3. Click 'Allow'.")
            print("4. Copy the authorization code.")
            webbrowser.open(authorize_url)
            auth_code = input("\nEnter the authorization code here: ").strip()

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

            print(f"DEBUG: Tokens to be saved: {tokens}")
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
        credentials = self.storage.get_tokens()
        if not credentials:
            logger.error("No credentials found")
            return None
        try:
            dbx = dropbox.Dropbox(
                oauth2_refresh_token=credentials["refresh_token"],
                app_key=credentials["app_key"],
                app_secret=credentials["app_secret"],
            )
            try:
                dbx.users_get_current_account()
            except dropbox.exceptions.AuthError:
                logger.error("Authentication error, unable to refresh token")
                return None
            logger.info("Successfully connected to Dropbox")
            return dbx
        except Exception as e:
            logger.error(f"Error connecting to Dropbox: {e}")
            return None


# Top-level aliases to support module-level imports
def authenticate_dropbox(*args, **kwargs):
    return Authenticator().authenticate_dropbox(*args, **kwargs)


def get_dropbox_client(*args, **kwargs):
    return Authenticator().get_dropbox_client(*args, **kwargs)


def setup_credentials(*args, **kwargs):
    return Authenticator().setup_credentials(*args, **kwargs)


def main():
    print("Welcome to Nova-PyDropbox Authentication Setup!")
    auth = Authenticator()
    storage = auth.storage
    existing_tokens = storage.get_tokens()

    if existing_tokens:
        print("\nExisting credentials found!")
        choice = input("Would you like to re-authenticate? (y/N): ").lower()
        if choice != "y":
            print("Skipping re-authentication.")
            return

    auth.authenticate_dropbox()


if __name__ == "__main__":
    main()
