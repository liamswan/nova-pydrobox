"""File operations module for nova-pydrobox."""

import hashlib
import logging
from pathlib import Path
from typing import List

import dropbox
import pandas as pd
from dropbox.files import FileMetadata, WriteMode
from tqdm import tqdm

from nova_pydrobox.operations.base import BaseOperations

logger = logging.getLogger(__name__)


class FileOperations(BaseOperations):
    """
    Class for handling Dropbox file operations.

    Provides functionality for:
    - File uploads (small and large files)
    - File downloads (small and large files)
    - Progress tracking
    - Chunked transfer handling
    - Directory synchronization

    Inherits from:
        BaseOperations: Core Dropbox operations functionality
    """

    def _read_file_chunks(self, local_path: str, file_size: int) -> bytes:
        """
        Read file in chunks for efficient memory usage.

        Args:
            local_path (str): Path to local file
            file_size (int): Size of file in bytes

        Returns:
            bytes: Concatenated file chunks

        Note:
            - Uses tqdm for progress visualization
            - Reads in chunks of CHUNK_SIZE (4MB)
        """
        chunks = []
        bytes_read = 0
        with open(local_path, "rb") as f:
            with tqdm(
                total=file_size,
                desc=f"Reading {Path(local_path).name}",
                unit="B",
                unit_scale=True,
            ) as pbar:
                while bytes_read < file_size:
                    chunk = f.read(min(self.CHUNK_SIZE, file_size - bytes_read))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    bytes_read += len(chunk)
                    pbar.update(len(chunk))
        return b"".join(chunks)

    def _upload_small_file(
        self, content: bytes, dropbox_path: str, mode: WriteMode, local_path: str
    ) -> FileMetadata:
        """
        Upload a small file (≤ 150MB) to Dropbox.

        Args:
            content (bytes): File content
            dropbox_path (str): Destination path in Dropbox
            mode (WriteMode): Upload mode (add/overwrite)
            local_path (str): Source file path

        Returns:
            FileMetadata: Metadata of uploaded file

        Note:
            Calculates SHA256 hash for content verification
        """
        hasher = hashlib.sha256()
        hasher.update(content)
        content_hash = hasher.hexdigest()

        return self.dbx.files_upload(
            content,
            dropbox_path,
            mode=mode,
            content_hash=content_hash,
        )

    def _upload_large_file(
        self, local_path: str, dropbox_path: str, mode: WriteMode
    ) -> FileMetadata:
        """
        Upload a large file (>150MB) to Dropbox using upload sessions.

        Args:
            local_path (str): Source file path
            dropbox_path (str): Destination path in Dropbox
            mode (WriteMode): Upload mode (add/overwrite)

        Returns:
            FileMetadata: Metadata of uploaded file

        Note:
            - Uses upload sessions for files >150MB
            - Shows progress with tqdm
            - Handles chunked uploads automatically
        """
        file_size = Path(local_path).stat().st_size
        with open(local_path, "rb") as f:
            with tqdm(
                total=file_size,
                desc=f"Uploading {Path(local_path).name}",
                unit="B",
                unit_scale=True,
            ) as pbar:
                # Start upload session
                session_start = self.dbx.files_upload_session_start(
                    f.read(self.CHUNK_SIZE)
                )
                pbar.update(self.CHUNK_SIZE)
                cursor = dropbox.files.UploadSessionCursor(
                    session_id=session_start.session_id, offset=f.tell()
                )
                commit = dropbox.files.CommitInfo(path=dropbox_path, mode=mode)
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
                return self.dbx.files_upload_session_finish(
                    f.read(self.CHUNK_SIZE), cursor, commit
                )

    def _upload_file(
        self, local_path: str, dropbox_path: str, mode: WriteMode
    ) -> FileMetadata:
        """
        Upload a file to Dropbox, choosing the appropriate method based on size.

        Args:
            local_path (str): Source file path
            dropbox_path (str): Destination path in Dropbox
            mode (WriteMode): Upload mode (add/overwrite)

        Returns:
            FileMetadata: Metadata of uploaded file

        Note:
            Automatically selects between small and large file upload methods
        """
        file_size = Path(local_path).stat().st_size
        if file_size <= 150 * 1024 * 1024:  # 150MB
            content = self._read_file_chunks(local_path, file_size)
            return self._upload_small_file(content, dropbox_path, mode, local_path)
        else:
            return self._upload_large_file(local_path, dropbox_path, mode)

    def upload(
        self, local_path: str, dropbox_path: str, overwrite: bool = False
    ) -> pd.DataFrame:
        """
        Upload a file or directory to Dropbox.

        Args:
            local_path (str): Path to local file or directory
            dropbox_path (str): Destination path in Dropbox
            overwrite (bool, optional): Whether to overwrite existing files. Defaults to False.

        Returns:
            pd.DataFrame: DataFrame containing metadata of uploaded files

        Raises:
            Exception: If upload fails

        Example:
            ```python
            # Upload single file
            result = ops.upload("local/path/file.txt", "/dropbox/path/file.txt")

            # Upload directory with overwrite
            result = ops.upload("local/folder", "/dropbox/folder", overwrite=True)
            ```
        """
        try:
            mode = WriteMode.overwrite if overwrite else WriteMode.add
            path = Path(local_path)
            results: List[dict] = []

            if path.is_file():
                result = self._upload_file(str(path), dropbox_path, mode)
                results.append(self._process_metadata(result))
            else:
                for file_path in path.rglob("*"):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(path)
                        dbx_path = str(Path(dropbox_path) / rel_path)
                        result = self._upload_file(str(file_path), dbx_path, mode)
                        results.append(self._process_metadata(result))

            return pd.DataFrame(results)
        except Exception as e:
            logger.error(f"Error uploading: {e}")
            raise

    def _download_file(self, dropbox_path: str, local_path: str) -> FileMetadata:
        """
        Download a file from Dropbox.

        Args:
            dropbox_path (str): Source path in Dropbox
            local_path (str): Destination path on local system

        Returns:
            FileMetadata: Metadata of downloaded file

        Note:
            - Creates parent directories if needed
            - Shows download progress
            - Automatically handles large files
        """
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
        """
        Download a large file (>150MB) from Dropbox using download sessions.

        Args:
            dropbox_path (str): Source path in Dropbox
            local_path (str): Destination path on local system

        Returns:
            FileMetadata: Metadata of downloaded file

        Note:
            - Uses download sessions for files >150MB
            - Shows progress with tqdm
            - Handles chunked downloads automatically
        """
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

                        cursor = dropbox.files.UploadSessionCursor(
                            session_id=result.session_id, offset=f.tell()
                        )
            return metadata

        except Exception as e:
            logger.error(f"Error downloading large file {dropbox_path}: {e}")
            raise

    def download(self, dropbox_path: str, local_path: str) -> pd.DataFrame:
        """
        Download a file or directory from Dropbox.

        Args:
            dropbox_path (str): Source path in Dropbox
            local_path (str): Destination path on local system

        Returns:
            pd.DataFrame: DataFrame containing metadata of downloaded files

        Raises:
            Exception: If download fails

        Example:
            ```python
            # Download single file
            result = ops.download("/dropbox/path/file.txt", "local/path/file.txt")

            # Download directory
            result = ops.download("/dropbox/folder", "local/folder")
            ```

        Note:
            - Creates local directories automatically
            - Preserves directory structure
            - Shows progress for each file
        """
        try:
            metadata = self.dbx.files_get_metadata(dropbox_path)
            results = []

            if isinstance(metadata, FileMetadata):
                result = self._download_file(dropbox_path, local_path)
                results.append(self._process_metadata(result))
            else:
                folder_contents = self.list_files(dropbox_path)
                for _, entry in folder_contents.iterrows():
                    if entry["type"] == "file":
                        rel_path = Path(entry["path"]).relative_to(dropbox_path)
                        local_file_path = str(Path(local_path) / rel_path)
                        result = self._download_file(entry["path"], local_file_path)
                        results.append(self._process_metadata(result))

            return pd.DataFrame(results)

        except Exception as e:
            logger.error(f"Error downloading {dropbox_path}: {e}")
            raise
