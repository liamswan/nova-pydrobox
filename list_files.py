import logging

import dropbox

from dropbox_auth import get_dropbox_client

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def list_files(path="", dbx=None):
    if dbx is None:
        dbx = get_dropbox_client()
        if dbx is None:
            print("Could not initialize Dropbox client")
            return
    try:
        entries = dbx.files_list_folder(path).entries

        print(f"\nContents of {path or '/'}: ")
        print("-" * 50)

        for entry in entries:
            if isinstance(entry, dropbox.files.FileMetadata):
                size_mb = entry.size / (1024 * 1024)
                print(f"📄 {entry.name:<30} {size_mb:.2f} MB")
            else:
                print(f"📁 {entry.name:<30} (folder)")

    except dropbox.exceptions.ApiError as e:
        logger.error(f"Error listing files: {e}")
        print(f"Error listing files: {e}")


def main():
    dbx = get_dropbox_client()

    if dbx:
        while True:
            print("\nOptions:")
            print("1. List root directory")
            print("2. List specific folder")
            print("3. Exit")

            choice = input("\nEnter your choice (1-3): ")

            if choice == "1":
                list_files(dbx=dbx)
            elif choice == "2":
                path = input("Enter the folder path (e.g., /Documents): ")
                list_files(path, dbx)
            elif choice == "3":
                print("Goodbye!")
                break
            else:
                print("Invalid choice. Please try again.")


if __name__ == "__main__":
    main()
