"""Folder operations module for nova-pydrobox."""

import logging

import dropbox
import pandas as pd
from dropbox.files import CreateFolderError, FolderMetadata

from nova_pydrobox.operations.base import BaseOperations

logger = logging.getLogger(__name__)


class FolderOperations(BaseOperations):
    """Class for handling Dropbox folder operations."""

    def create_folder(self, path: str) -> pd.DataFrame:
        """Create a new folder at the specified path.

        Args:
            path: The Dropbox path where the folder should be created.

        Returns:
            DataFrame containing the metadata of the created folder.
        """
        try:
            response = self.dbx.files_create_folder_v2(path)
            result = self._process_metadata(response.metadata)
            return pd.DataFrame([result])
        except dropbox.exceptions.ApiError as e:
            if (
                isinstance(e.error, CreateFolderError)
                and e.error.is_path()
                and e.error.get_path().is_conflict()
            ):
                # Handle folder already exists case
                metadata = self.dbx.files_get_metadata(path)
                result = self._process_metadata(metadata)
                return pd.DataFrame([result])
            logger.error(f"Error creating folder at {path}: {e}")
            raise

    def get_folder_size(self, path: str = "") -> int:
        """Calculate the total size of a folder.

        Args:
            path: The Dropbox path of the folder.

        Returns:
            Total size of the folder in bytes.
        """
        try:
            folder_contents = self.list_files(path)
            return folder_contents["size"].sum()
        except dropbox.exceptions.ApiError as e:
            logger.error(f"Error calculating folder size for {path}: {e}")
            raise

    def get_folder_structure(self, path: str = "") -> pd.DataFrame:
        """Get the complete folder structure starting from the specified path.

        Args:
            path: The Dropbox path to start from.

        Returns:
            DataFrame containing the folder structure with paths and metadata.
        """
        try:
            return self.list_files(path, recursive=True)
        except dropbox.exceptions.ApiError as e:
            logger.error(f"Error getting folder structure for {path}: {e}")
            raise

    def is_empty(self, path: str) -> bool:
        """Check if a folder is empty.

        Args:
            path: The Dropbox path of the folder.

        Returns:
            True if the folder is empty, False otherwise.
        """
        try:
            folder_contents = self.list_files(path)
            return len(folder_contents) == 0
        except dropbox.exceptions.ApiError as e:
            logger.error(f"Error checking if folder {path} is empty: {e}")
            raise

    def get_folder_metadata(self, path: str) -> pd.DataFrame:
        """Get metadata for a specific folder.

        Args:
            path: The Dropbox path of the folder.

        Returns:
            DataFrame containing the folder's metadata.
        """
        try:
            metadata = self.dbx.files_get_metadata(path)
            if not isinstance(metadata, FolderMetadata):
                raise ValueError(f"{path} is not a folder")
            result = self._process_metadata(metadata)
            return pd.DataFrame([result])
        except (dropbox.exceptions.ApiError, ValueError) as e:
            logger.error(f"Error getting folder metadata for {path}: {e}")
            raise
