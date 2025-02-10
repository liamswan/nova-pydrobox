import sys

from nova_pydrobox import Authenticator, FolderOperations


def main():
    try:
        # Print Python version and environment info
        print(f"Python version: {sys.version}")

        # Run authentication
        auth = Authenticator()
        auth.authenticate_dropbox()
        print("Authentication completed")

        # Initialize client with debug
        dbx = FolderOperations()
        print("Dropbox client initialized")

        # List files with explicit path
        print("Attempting to list files...")
        files = dbx.list_files("/")

        if len(files) == 0:
            print("No files found - verify authentication")
        else:
            print(f"Found {len(files)} files:")
            print(files)

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        print(f"Error type: {type(e)}")


if __name__ == "__main__":
    main()
