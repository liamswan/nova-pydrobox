"""Base operations module for nova-pydrobox."""

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Union

import dropbox
import pandas as pd
from dropbox.files import (  # Add FileStatus
    FileMetadata,
    FileStatus,
    FolderMetadata,
    ListFolderResult,
)

from nova_pydrobox.auth.authenticator import get_dropbox_client

logger = logging.getLogger(__name__)


class FileType(Enum):
    """
    Enumeration of supported file types for filtering.

    Attributes:
        ALL: All file types
        DOCUMENT: Document files
        FOLDER: Folders/directories
        IMAGE: Image files
        VIDEO: Video files
        AUDIO: Audio files
    """

    ALL = "all"
    DOCUMENT = "document"
    FOLDER = "folder"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


@dataclass
class FileFilter:
    """
    Filter criteria for file operations.

    Attributes:
        file_type (FileType): Type of files to include. Defaults to FileType.ALL.
        min_size (Optional[int]): Minimum file size in bytes. Defaults to None.
        max_size (Optional[int]): Maximum file size in bytes. Defaults to None.
        recursive (bool): Whether to search recursively. Defaults to False.
    """

    file_type: FileType = FileType.ALL
    min_size: Optional[int] = None
    max_size: Optional[int] = None
    recursive: bool = False


class BaseOperations:
    """
    Base class for Dropbox file operations.

    Provides core functionality for file operations including:
    - File listing and searching
    - File/folder manipulation (copy, move, delete)
    - Metadata processing
    - File hash calculation

    Attributes:
        CHUNK_SIZE (int): Size of chunks for file operations (4MB)
        dbx (dropbox.Dropbox): Authenticated Dropbox client
        max_workers (int): Maximum number of concurrent operations
    """

    CHUNK_SIZE = 4 * 1024 * 1024

    def __init__(self, max_workers: int = 4, dbx_client=None):
        """
        Initialize BaseOperations with Dropbox client.

        Args:
            max_workers (int, optional): Maximum concurrent operations. Defaults to 4.
            dbx_client (Optional[dropbox.Dropbox]): Existing Dropbox client. Defaults to None.

        Raises:
            ConnectionError: If Dropbox client initialization fails
        """
        self.dbx = dbx_client if dbx_client else get_dropbox_client()
        if not self.dbx:
            raise ConnectionError("Could not initialize Dropbox client")
        self.max_workers = max_workers

    def _calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate SHA256 hash of a file.

        Args:
            file_path (str): Path to the file

        Returns:
            str: Hexadecimal representation of the SHA256 hash

        Note:
            Uses chunked reading for memory efficiency
        """
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(self.CHUNK_SIZE), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _process_metadata(self, metadata: Union[FileMetadata, FolderMetadata]) -> dict:
        """
        Process Dropbox metadata into standardized format.

        Args:
            metadata (Union[FileMetadata, FolderMetadata]): Dropbox metadata object

        Returns:
            dict: Standardized metadata dictionary with keys:
                - name: File/folder name
                - path: Full path (lowercase)
                - type: 'file' or 'folder'
                - size: Size in bytes (0 for folders)
                - modified: ISO 8601 timestamp
                - hash: Content hash (files only)
        """
        modified = getattr(metadata, "client_modified", None)
        if isinstance(modified, datetime):
            modified = modified.isoformat().replace("+00:00", "Z")
        return {
            "name": metadata.name,
            "path": metadata.path_lower,
            "type": "folder" if isinstance(metadata, FolderMetadata) else "file",
            "size": getattr(metadata, "size", 0)
            if isinstance(metadata, FileMetadata)
            else 0,
            "modified": modified,
            "hash": getattr(metadata, "content_hash", None),
        }

    def _process_listing_result(self, result: ListFolderResult) -> pd.DataFrame:
        """
        Convert Dropbox listing result to DataFrame.

        Args:
            result (ListFolderResult): Dropbox folder listing result

        Returns:
            pd.DataFrame: DataFrame containing file/folder metadata
        """
        entries: List[dict] = []
        for entry in result.entries:
            entry_dict = self._process_metadata(entry)
            entries.append(entry_dict)
        return pd.DataFrame(entries)

    def list_files(
        self, path: str = "", filter_criteria: Optional[FileFilter] = None
    ) -> pd.DataFrame:
        """
        List files and folders in specified Dropbox path.

        Args:
            path (str, optional): Dropbox path to list. Defaults to root.
            filter_criteria (Optional[FileFilter]): Filtering options. Defaults to None.

        Returns:
            pd.DataFrame: DataFrame containing filtered file/folder metadata

        Raises:
            dropbox.exceptions.ApiError: If Dropbox API request fails

        Example:
            ```python
            # List all files recursively
            files = ops.list_files("/", FileFilter(recursive=True))

            # List only images
            images = ops.list_files("/photos", FileFilter(file_type=FileType.IMAGE))
            ```
        """
        try:
            if path == "/":
                path = ""  # Dropbox API requires root as empty string

            has_more = True
            cursor = None
            all_entries = []

            while has_more:
                if cursor:
                    result = self.dbx.files_list_folder_continue(cursor)
                else:
                    result = self.dbx.files_list_folder(
                        path,
                        recursive=filter_criteria.recursive
                        if filter_criteria
                        else False,
                    )

                df = self._process_listing_result(result)

                if filter_criteria:
                    if filter_criteria.file_type != FileType.ALL:
                        df = df[df["type"] == filter_criteria.file_type.value]
                    if filter_criteria.min_size:
                        df = df[df["size"] >= filter_criteria.min_size]
                    if filter_criteria.max_size:
                        df = df[df["size"] <= filter_criteria.max_size]

                all_entries.append(df)
                has_more = result.has_more
                cursor = result.cursor

            return pd.concat(all_entries, ignore_index=True)

        except dropbox.exceptions.ApiError as e:
            logger.error(f"Error listing files: {e}")
            raise

    def delete(self, path: str) -> bool:
        """
        Delete file or folder at specified path.

        Args:
            path (str): Dropbox path to delete

        Returns:
            bool: True if deletion successful

        Raises:
            dropbox.exceptions.ApiError: If deletion fails
        """
        try:
            self.dbx.files_delete_v2(path)
            logger.info(f"Successfully deleted {path}")
            return True
        except dropbox.exceptions.ApiError as e:
            logger.error(f"Error deleting {path}: {e}")
            raise

    def move(self, from_path: str, to_path: str) -> pd.DataFrame:
        """
        Move file or folder to new location.

        Args:
            from_path (str): Source Dropbox path
            to_path (str): Destination Dropbox path

        Returns:
            pd.DataFrame: DataFrame containing moved item metadata

        Raises:
            dropbox.exceptions.ApiError: If move operation fails

        Note:
            Automatically renames on conflict
        """
        try:
            metadata = self.dbx.files_move_v2(
                from_path, to_path, allow_shared_folder=True, autorename=True
            ).metadata
            result = self._process_metadata(metadata)
            return pd.DataFrame([result])
        except dropbox.exceptions.ApiError as e:
            logger.error(f"Error moving from {from_path} to {to_path}: {e}")
            raise

    def copy(self, from_path: str, to_path: str) -> pd.DataFrame:
        """
        Copy file or folder to new location.

        Args:
            from_path (str): Source Dropbox path
            to_path (str): Destination Dropbox path

        Returns:
            pd.DataFrame: DataFrame containing copied item metadata

        Raises:
            dropbox.exceptions.ApiError: If copy operation fails

        Note:
            Automatically renames on conflict
        """
        try:
            metadata = self.dbx.files_copy_v2(
                from_path, to_path, allow_shared_folder=True, autorename=True
            ).metadata
            result = self._process_metadata(metadata)
            return pd.DataFrame([result])
        except dropbox.exceptions.ApiError as e:
            logger.error(f"Error copying from {from_path} to {to_path}: {e}")
            raise

    def rename(self, from_path: str, new_name: str) -> pd.DataFrame:
        """
        Rename file or folder.

        Args:
            from_path (str): Current Dropbox path
            new_name (str): New name (not path)

        Returns:
            pd.DataFrame: DataFrame containing renamed item metadata

        Raises:
            dropbox.exceptions.ApiError: If rename operation fails

        Note:
            Preserves parent directory
        """
        try:
            parent_path = str(Path(from_path).parent)
            to_path = str(Path(parent_path) / new_name)
            metadata = self.dbx.files_move_v2(
                from_path, to_path, allow_shared_folder=True, autorename=True
            ).metadata
            result = self._process_metadata(metadata)
            return pd.DataFrame([result])
        except dropbox.exceptions.ApiError as e:
            logger.error(f"Error renaming {from_path} to {new_name}: {e}")
            raise

    def search(
        self, query: str, path: str = "", filter_criteria: FileFilter = None
    ) -> pd.DataFrame:
        """
        Search for files and folders matching query.

        Args:
            query (str): Search query string
            path (str, optional): Root path for search. Defaults to entire Dropbox.
            filter_criteria (FileFilter, optional): Filtering options. Defaults to None.

        Returns:
            pd.DataFrame: DataFrame containing search results

        Raises:
            dropbox.exceptions.ApiError: If search operation fails

        Example:
            ```python
            # Search for images in Photos folder
            results = ops.search("vacation", "/Photos",
                               FileFilter(file_type=FileType.IMAGE))
            ```
        """
        try:
            matches = []
            has_more = True
            cursor = None

            while has_more:
                if cursor:
                    result = self.dbx.files_search_continue_v2(cursor)
                else:
                    result = self.dbx.files_search_v2(
                        query,
                        options=dropbox.files.SearchOptions(
                            path=path if path else None,
                            max_results=1000,
                            file_status=FileStatus.active,  # Use enum instead of string
                        ),
                    )

                entries = [match.metadata for match in result.matches]
                df = pd.DataFrame([self._process_metadata(entry) for entry in entries])

                if filter_criteria:
                    if filter_criteria.file_type != FileType.ALL:
                        df = df[df["type"] == filter_criteria.file_type.value]
                    if filter_criteria.min_size:
                        df = df[df["size"] >= filter_criteria.min_size]
                    if filter_criteria.max_size:
                        df = df[df["size"] <= filter_criteria.max_size]

                matches.append(df)
                has_more = result.has_more
                cursor = result.cursor

            return pd.concat(matches, ignore_index=True) if matches else pd.DataFrame()

        except dropbox.exceptions.ApiError as e:
            logger.error(f"Error searching for {query}: {e}")
            raise
