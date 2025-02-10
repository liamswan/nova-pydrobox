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
    ALL = "all"
    DOCUMENT = "document"
    FOLDER = "folder"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


@dataclass
class FileFilter:
    file_type: FileType = FileType.ALL
    min_size: Optional[int] = None
    max_size: Optional[int] = None
    recursive: bool = False


class BaseOperations:
    CHUNK_SIZE = 4 * 1024 * 1024

    def __init__(self, max_workers: int = 4, dbx_client=None):
        self.dbx = dbx_client if dbx_client else get_dropbox_client()
        if not self.dbx:
            raise ConnectionError("Could not initialize Dropbox client")
        self.max_workers = max_workers

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(self.CHUNK_SIZE), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _process_metadata(self, metadata: Union[FileMetadata, FolderMetadata]) -> dict:
        """Process Dropbox metadata into a standardized dictionary format."""
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
        """Process Dropbox listing result into a pandas DataFrame."""
        entries: List[dict] = []
        for entry in result.entries:
            entry_dict = self._process_metadata(entry)
            entries.append(entry_dict)
        return pd.DataFrame(entries)

    def list_files(
        self, path: str = "", filter_criteria: Optional[FileFilter] = None
    ) -> pd.DataFrame:
        """List files and folders in the specified Dropbox path."""
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
        """Delete a file or folder at the specified path."""
        try:
            self.dbx.files_delete_v2(path)
            logger.info(f"Successfully deleted {path}")
            return True
        except dropbox.exceptions.ApiError as e:
            logger.error(f"Error deleting {path}: {e}")
            raise

    def move(self, from_path: str, to_path: str) -> pd.DataFrame:
        """Move a file or folder to a new location."""
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
        """Copy a file or folder to a new location."""
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
        """Rename a file or folder."""
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
        """Search for files and folders matching the query."""
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
