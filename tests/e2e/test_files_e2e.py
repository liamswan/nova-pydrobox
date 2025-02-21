"""End-to-end tests for file operations."""
import os
from pathlib import Path

import pandas as pd
import pytest

from nova_pydrobox.operations.files import FileOperations

@pytest.mark.e2e
def test_file_upload_download_cycle(
    e2e_auth, e2e_dropbox_client, test_file, e2e_test_path, tmp_path
):
    """
    Test complete file upload and download cycle using real Dropbox API.
    
    This test:
    1. Uploads a local file to Dropbox
    2. Verifies the upload was successful
    3. Downloads the file to a new location
    4. Verifies the downloaded content matches original
    """
    # Initialize file operations
    file_ops = FileOperations(dbx_client=e2e_dropbox_client)
    
    # Setup test paths
    dropbox_path = f"{e2e_test_path}/test_file.txt"
    download_path = tmp_path / "downloaded.txt"
    
    # Test uploading
    original_content = test_file.read_text()
    result = file_ops.upload(str(test_file), dropbox_path)
    
    # Verify upload result
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert result.iloc[0]["path"].lower() == dropbox_path.lower()
    
    # Test downloading
    result = file_ops.download(dropbox_path, str(download_path))
    
    # Verify download result
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert Path(download_path).exists()
    
    # Compare contents
    downloaded_content = Path(download_path).read_text()
    assert downloaded_content == original_content

@pytest.mark.e2e
def test_folder_upload_download_cycle(
    e2e_auth, e2e_dropbox_client, test_folder, e2e_test_path, tmp_path
):
    """
    Test complete folder upload and download cycle using real Dropbox API.
    
    This test:
    1. Uploads a local folder structure to Dropbox
    2. Verifies all files were uploaded correctly
    3. Downloads the folder to a new location
    4. Verifies the downloaded structure matches original
    """
    # Initialize file operations
    file_ops = FileOperations(dbx_client=e2e_dropbox_client)
    
    # Setup test paths
    dropbox_path = f"{e2e_test_path}/test_folder"
    download_path = tmp_path / "downloaded_folder"
    
    # Test uploading folder
    result = file_ops.upload(str(test_folder), dropbox_path)
    
    # Verify upload result
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 3  # file1.txt, file2.txt, file3.txt
    
    # Test downloading folder
    result = file_ops.download(dropbox_path, str(download_path))
    
    # Verify download result
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 3
    
    # Compare directory structures
    original_files = {str(p.relative_to(test_folder)) for p in test_folder.rglob("*.txt")}
    downloaded_files = {str(p.relative_to(download_path)) for p in download_path.rglob("*.txt")}
    assert original_files == downloaded_files
    
    # Compare contents of each file
    for file_path in original_files:
        original_content = (test_folder / file_path).read_text()
        downloaded_content = (download_path / file_path).read_text()
        assert downloaded_content == original_content

@pytest.mark.e2e
def test_large_file_operations(
    e2e_auth, e2e_dropbox_client, tmp_path, e2e_test_path
):
    """
    Test operations with files larger than the chunked upload threshold.
    
    This test:
    1. Creates a large test file (>150MB)
    2. Uploads it using chunked upload
    3. Downloads it using chunked download
    4. Verifies the content integrity
    """
    # Initialize file operations
    file_ops = FileOperations(dbx_client=e2e_dropbox_client)
    
    # Create large test file (200MB)
    large_file = tmp_path / "large_file.bin"
    size = 200 * 1024 * 1024  # 200MB
    chunk_size = 1024 * 1024  # 1MB chunks for writing
    
    with large_file.open("wb") as f:
        remaining = size
        while remaining > 0:
            write_size = min(chunk_size, remaining)
            f.write(os.urandom(write_size))
            remaining -= write_size
    
    # Setup test paths
    dropbox_path = f"{e2e_test_path}/large_file.bin"
    download_path = tmp_path / "downloaded_large.bin"
    
    # Test uploading
    result = file_ops.upload(str(large_file), dropbox_path)
    
    # Verify upload result
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert result.iloc[0]["size"] == size
    
    # Test downloading
    result = file_ops.download(dropbox_path, str(download_path))
    
    # Verify download result
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert download_path.exists()
    assert download_path.stat().st_size == size
    
    # Compare file hashes to verify integrity
    assert _get_file_hash(large_file) == _get_file_hash(download_path)

def _get_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    import hashlib
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()
