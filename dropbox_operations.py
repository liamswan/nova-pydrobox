import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import dropbox
import pandas as pd
from dropbox.files import FileMetadata, FolderMetadata, ListFolderResult, WriteMode
from tqdm import tqdm

from dropbox_auth import get_dropbox_client

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


class DropboxOperations:
    CHUNK_SIZE = 4 * 1024 * 1024

    def __init__(self, max_workers: int = 4):
        self.dbx = get_dropbox_client()
        if not self.dbx:
            raise ConnectionError("Could not initialize Dropbox client")
        self.max_workers = max_workers

    def _calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate SHA-256 hash of a file.

        Args:
            file_path: Path to the file

        Returns:
            str: Hexadecimal hash of the file
        """
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(self.CHUNK_SIZE), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _process_listing_result(self, result: ListFolderResult) -> pd.DataFrame:
        entries = []
        for entry in result.entries:
            entry_dict = {
                "name": entry.name,
                "path": entry.path_lower,
                "type": "folder" if isinstance(entry, FolderMetadata) else "file",
                "size": getattr(entry, "size", 0)
                if isinstance(entry, FileMetadata)
                else 0,
                "modified": getattr(entry, "client_modified", None),
                "hash": getattr(entry, "content_hash", None),
            }
            entries.append(entry_dict)
        return pd.DataFrame(entries)

    def list_files(self, path: str = "", filter_criteria: FileFilter = None):
        try:
            has_more = True
            cursor = None
            all_entries = []

            with tqdm(desc="Listing files", unit=" entries") as pbar:
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
                    pbar.update(len(result.entries))

                    has_more = result.has_more
                    cursor = result.cursor

            return pd.concat(all_entries, ignore_index=True)

        except dropbox.exceptions.ApiError as e:
            logger.error(f"Error listing files: {e}")
            logger.error(f"Dropbox API error: {e}")
            raise

    def _upload_file(
        self, local_path: str, dropbox_path: str, mode: WriteMode
    ) -> FileMetadata:
        file_size = Path(local_path).stat().st_size

        if file_size <= 150 * 1024 * 1024:
            with open(local_path, "rb") as f:
                with tqdm(
                    total=file_size,
                    desc=f"Uploading {Path(local_path).name}",
                    unit="B",
                    unit_scale=True,
                ) as pbar:
                    chunks = []
                    bytes_read = 0
                    while bytes_read < file_size:
                        chunk = f.read(min(self.CHUNK_SIZE, file_size - bytes_read))
                        if not chunk:
                            break
                        chunks.append(chunk)
                        bytes_read += len(chunk)
                        pbar.update(len(chunk))

                    content = b"".join(chunks)
                    return self.dbx.files_upload(
                        content,
                        dropbox_path,
                        mode=mode,
                        content_hash=self._calculate_file_hash(local_path),
                    )
        return self._upload_large_file(local_path, dropbox_path, mode)

    def _upload_large_file(
        self, local_path: str, dropbox_path: str, mode: WriteMode
    ) -> FileMetadata:
        file_size = Path(local_path).stat().st_size

        with open(local_path, "rb") as f:
            with tqdm(
                total=file_size,
                desc=f"Uploading {Path(local_path).name}",
                unit="B",
                unit_scale=True,
            ) as pbar:
                upload_session_start_result = self.dbx.files_upload_session_start(
                    f.read(self.CHUNK_SIZE)
                )
                pbar.update(self.CHUNK_SIZE)

                cursor = dropbox.files.UploadSessionCursor(
                    session_id=upload_session_start_result.session_id, offset=f.tell()
                )

                commit = dropbox.files.CommitInfo(
                    path=dropbox_path,
                    mode=mode,
                    content_hash=self._calculate_file_hash(local_path),
                )

                while f.tell() < file_size:
                    if (file_size - f.tell()) <= self.CHUNK_SIZE:
                        return self.dbx.files_upload_session_finish(
                            f.read(self.CHUNK_SIZE), cursor, commit
                        )
                    else:
                        self.dbx.files_upload_session_append_v2(
                            f.read(self.CHUNK_SIZE), cursor
                        )
                        cursor.offset = f.tell()
                        pbar.update(self.CHUNK_SIZE)

    def upload(
        self, local_path: str, dropbox_path: str, overwrite: bool = False
    ) -> pd.DataFrame:
        try:
            mode = WriteMode.overwrite if overwrite else WriteMode.add
            path = Path(local_path)
            results = []

            if path.is_file():
                result = self._upload_file(str(path), dropbox_path, mode)
                results.append(self._process_metadata(result))
            else:
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = []
                    for file_path in path.rglob("*"):
                        if file_path.is_file():
                            rel_path = file_path.relative_to(path)
                            dbx_path = str(Path(dropbox_path) / rel_path)
                            futures.append(
                                executor.submit(
                                    self._upload_file, str(file_path), dbx_path, mode
                                )
                            )

                    for future in tqdm(futures, desc="Uploading files"):
                        results.append(self._process_metadata(future.result()))

            return pd.DataFrame(results)

        except Exception as e:
            logger.error(f"Error uploading: {e}")
        except IOError as e:
            logger.error(f"IO error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def _download_file(self, dropbox_path: str, local_path: str) -> FileMetadata:
        """Download a single file from Dropbox."""
        try:
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            metadata = self.dbx.files_get_metadata(dropbox_path)

            if isinstance(metadata, FileMetadata) and metadata.size > 150 * 1024 * 1024:
                return self._download_large_file(dropbox_path, local_path)

            with open(local_path, "wb") as f:
                metadata, response = self.dbx.files_download(dropbox_path)
                with tqdm(
                    total=metadata.size,
                    desc=f"Downloading {Path(local_path).name}",
                    unit="B",
                    unit_scale=True,
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=self.CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            return metadata

        except Exception as e:
            logger.error(f"Error downloading {dropbox_path}: {e}")
            raise

    def _download_large_file(self, dropbox_path: str, local_path: str) -> FileMetadata:
        """Download a large file in chunks."""
        try:
            metadata = self.dbx.files_get_metadata(dropbox_path)

            with open(local_path, "wb") as f:
                with tqdm(
                    total=metadata.size,
                    desc=f"Downloading {Path(local_path).name}",
                    unit="B",
                    unit_scale=True,
                ) as pbar:
                    cursor = None
                    while True:
                        if cursor is None:
                            metadata, result = self.dbx.files_download_session_start()
                        else:
                            result = self.dbx.files_download_session_append(cursor)

                        data = result.content
                        f.write(data)
                        pbar.update(len(data))

                        if len(data) < self.CHUNK_SIZE:
                            break

                        cursor = dropbox.files.DownloadSessionCursor(
                            session_id=result.session_id, offset=f.tell()
                        )
            return metadata

        except Exception as e:
            logger.error(f"Error downloading large file {dropbox_path}: {e}")
            raise

    def download(self, dropbox_path: str, local_path: str) -> pd.DataFrame:
        """
        Download a file or folder from Dropbox.

        Args:
            dropbox_path: Path in Dropbox to download from
            local_path: Local path to save to

        Returns:
            DataFrame containing metadata of downloaded files
        """
        try:
            metadata = self.dbx.files_get_metadata(dropbox_path)
            results = []

            if isinstance(metadata, FileMetadata):
                result = self._download_file(dropbox_path, local_path)
                results.append(self._process_metadata(result))
            else:
                folder_contents = self.list_files(dropbox_path)
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = []
                    for _, entry in folder_contents.iterrows():
                        if entry["type"] == "file":
                            rel_path = Path(entry["path"]).relative_to(dropbox_path)
                            local_file_path = str(Path(local_path) / rel_path)
                            futures.append(
                                executor.submit(
                                    self._download_file, entry["path"], local_file_path
                                )
                            )

                    for future in tqdm(futures, desc="Downloading files"):
                        results.append(self._process_metadata(future.result()))

            return pd.DataFrame(results)

        except Exception as e:
            logger.error(f"Error downloading {dropbox_path}: {e}")
            raise
