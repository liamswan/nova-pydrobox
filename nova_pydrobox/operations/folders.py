"""Folder operations module for nova-pydrobox."""

import logging

import dropbox
import pandas as pd
from dropbox.files import CreateFolderError, FolderMetadata

from nova_pydrobox.operations.base import BaseOperations, FileFilter

logger = logging.getLogger(__name__)


class FolderOperations(BaseOperations):
    """
    Class for handling Dropbox folder operations.

    Provides functionality for:
    - Folder creation and management
    - Size calculations
    - Structure analysis
    - Metadata retrieval
    - Empty folder detection

    Inherits from:
        BaseOperations: Core Dropbox operations functionality
    """

    def create_folder(self, path: str) -> pd.DataFrame:
        """
        Create a new folder at the specified path.

        Args:
            path (str): The Dropbox path where the folder should be created

        Returns:
            pd.DataFrame: DataFrame containing the metadata of the created folder

        Raises:
            dropbox.exceptions.ApiError: If folder creation fails

        Note:
            - Handles cases where folder already exists
            - Returns metadata even if folder pre-exists

        Example:
            ```python
            # Create a new folder
            result = ops.create_folder("/Documents/NewFolder")
            print(result["path"].iloc[0])  # Show created folder path
            ```
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
        """
        Calculate the total size of a folder.

        Args:
            path (str, optional): The Dropbox path of the folder. Defaults to root.

        Returns:
            int: Total size of the folder in bytes

        Raises:
            dropbox.exceptions.ApiError: If size calculation fails

        Note:
            - Recursively calculates size of all contents
            - Includes all nested files and folders

        Example:
            ```python
            # Get size of Documents folder
            size = ops.get_folder_size("/Documents")
            print(f"Size: {size / (1024*1024):.2f} MB")
            ```
        """
        try:
            folder_contents = self.list_files(path)
            return folder_contents["size"].sum()
        except dropbox.exceptions.ApiError as e:
            logger.error(f"Error calculating folder size for {path}: {e}")
            raise

    def get_folder_structure(self, path: str = "") -> pd.DataFrame:
        """
        Get the complete folder structure starting from the specified path.

        Args:
            path (str, optional): The Dropbox path to start from. Defaults to root.

        Returns:
            pd.DataFrame: DataFrame containing the folder structure with columns:
                - name: File/folder name
                - path: Full Dropbox path
                - type: 'file' or 'folder'
                - size: Size in bytes
                - modified: Last modification time
                - hash: Content hash (files only)

        Raises:
            dropbox.exceptions.ApiError: If structure retrieval fails

        Note:
            - Returns recursive listing of all contents
            - Includes files and folders at all levels
            - Preserves folder hierarchy

        Example:
            ```python
            # Get complete structure of Photos folder
            structure = ops.get_folder_structure("/Photos")
            # Show all folders
            folders = structure[structure["type"] == "folder"]
            ```
        """
        try:
            return self.list_files(path, filter_criteria=FileFilter(recursive=True))
        except dropbox.exceptions.ApiError as e:
            logger.error(f"Error getting folder structure for {path}: {e}")
            raise

    def is_empty(self, path: str) -> bool:
        """
        Check if a folder is empty.

        Args:
            path (str): The Dropbox path of the folder

        Returns:
            bool: True if the folder is empty, False otherwise

        Raises:
            dropbox.exceptions.ApiError: If check fails

        Note:
            - Considers both files and subfolders
            - Hidden files are included in check

        Example:
            ```python
            # Check if Downloads folder is empty
            if ops.is_empty("/Downloads"):
                print("Downloads folder is empty")
            ```
        """
        try:
            folder_contents = self.list_files(path)
            return len(folder_contents) == 0
        except dropbox.exceptions.ApiError as e:
            logger.error(f"Error checking if folder {path} is empty: {e}")
            raise

    def get_folder_metadata(self, path: str) -> pd.DataFrame:
        """
        Get metadata for a specific folder.

        Args:
            path (str): The Dropbox path of the folder

        Returns:
            pd.DataFrame: DataFrame containing the folder's metadata with columns:
                - name: Folder name
                - path: Full Dropbox path
                - type: Always 'folder'
                - size: 0 (folders have no size)
                - modified: Last modification time

        Raises:
            dropbox.exceptions.ApiError: If metadata retrieval fails
            ValueError: If path points to a file instead of folder

        Note:
            - Validates that path points to a folder
            - Returns standardized metadata format

        Example:
            ```python
            # Get metadata for Documents folder
            metadata = ops.get_folder_metadata("/Documents")
            print(f"Last modified: {metadata['modified'].iloc[0]}")
            ```
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
