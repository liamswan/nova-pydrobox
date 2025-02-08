import logging
import webbrowser

import dropbox

from token_storage import TokenStorage

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def setup_credentials():
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
    print("4. Click 'Create app'")
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


def authenticate_dropbox():
    app_key, app_secret = setup_credentials()
    try:
        flow = dropbox.DropboxOAuth2FlowNoRedirect(
            consumer_key=app_key,
            consumer_secret=app_secret,
            token_access_type="offline",
            use_pkce=True,
        )

        authorize_url = flow.start()
        print("\n1. I'll open the Dropbox authentication page in your browser.")
        print("2. Select an acount. (you might have to log in first)")
        print("2. Click 'Allow.")
        print("3. Copy the authorization code.")
        webbrowser.open(authorize_url)
        auth_code = input("\nEnter the authorization code here: ").strip()

        oauth_result = flow.finish(auth_code)

        storage = TokenStorage()
        tokens = {
            "app_key": app_key,
            "app_secret": app_secret,
            "access_token": oauth_result.access_token,
            "refresh_token": oauth_result.refresh_token,
        }

        if storage.save_tokens(tokens):
            print("\nAuthentication successful! Tokens securely stored.")
            return True
        else:
            print("\nError saving tokens.")
            return False
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        print(f"\nAuthentication failed: {e}")
        return False


def get_dropbox_client():
    """Initialize and return Dropbox client using stored credentials"""
    storage = TokenStorage()
    credentials = storage.get_tokens()

    if not credentials:
        logger.error("No credentials found")
        return None

    try:
        dbx = dropbox.Dropbox(
            oauth2_refresh_token=credentials["refresh_token"],
            app_key=credentials["app_key"],
            app_secret=credentials["app_secret"],
        )

        # Test connection and handle token refresh
        try:
            dbx.users_get_current_account()
        except dropbox.exceptions.AuthError:
            # If we get an auth error, try refreshing the access token
            dbx.refresh_access_token()

        logger.info("Successfully connected to Dropbox")
        return dbx
    except Exception as e:
        logger.error(f"Error connecting to Dropbox: {e}")
        return None


def main():
    print("Welcome to Nova-PyDropbox Authentication Setup!")

    storage = TokenStorage()
    existing_tokens = storage.get_tokens()

    if existing_tokens:
        print("\nExisting credentials found!")
        choice = input("Would you like to re-authenticate? (y/N): ").lower()

        if choice == "y":
            storage.clear_tokens()
            authenticate_dropbox()
        else:
            print("\nKeeping existing credentials.")
    else:
        authenticate_dropbox()


if __name__ == "__main__":
    main()
