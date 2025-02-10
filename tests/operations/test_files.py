"""Tests for the file operations module."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import dropbox
import pandas as pd
import pytest
from dropbox.files import FileMetadata, FolderMetadata, WriteMode

from nova_pydrobox.operations.files import FileOperations


@pytest.fixture
def mock_dropbox_client():
    with patch("nova_pydrobox.auth.authenticator.get_dropbox_client") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def file_ops(mock_dropbox_client):
    return FileOperations()


@pytest.fixture
def test_file(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("test content")
    return file_path


def test_read_file_chunks(file_ops, test_file):
    """Test reading file in chunks."""
    content = file_ops._read_file_chunks(str(test_file), test_file.stat().st_size)
    assert content == b"test content"


def test_upload_small_file(file_ops, test_file, mock_dropbox_client):
    """Test uploading a small file."""
    test_content = b"test content"
    # Use dropbox.files.get_content_hash instead
    file_ops._calculate_file_hash = MagicMock(
        return_value=dropbox.files.get_content_hash(test_content)
    )
    mock_dropbox_client.files_upload.return_value = FileMetadata(
        name="test.txt",
        path_lower="/test.txt",
        client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
        size=100,
        content_hash="a" * 64,
    )

    result = file_ops._upload_small_file(
        test_content, "/test.txt", WriteMode.add, str(test_file)
    )

    assert isinstance(result, FileMetadata)
    assert result.name == "test.txt"
    assert result.path_lower == "/test.txt"
    mock_dropbox_client.files_upload.assert_called_once()


def test_upload_large_file(file_ops, test_file, mock_dropbox_client):
    """Test uploading a large file."""
    # Mock file size to be > 150MB
    with patch("pathlib.Path.stat") as mock_stat:
        mock_stat.return_value.st_size = 200 * 1024 * 1024  # 200MB
        session_id = "test_session"
        metadata = FileMetadata(
            name="test.txt",
            path_lower="/test.txt",
            client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
            size=100,
            content_hash="a" * 64,  # Use valid hash length
        )

        mock_dropbox_client.files_upload_session_start.return_value = MagicMock(
            session_id=session_id
        )
        mock_dropbox_client.files_upload_session_finish.return_value = metadata

        result = file_ops._upload_large_file(str(test_file), "/test.txt", WriteMode.add)
        assert isinstance(result, FileMetadata)
        assert result.name == "test.txt"
        mock_dropbox_client.files_upload_session_start.assert_called_once()


def test_upload_file_small(file_ops, test_file):
    """Test upload_file with a small file."""
    with patch.object(file_ops, "_upload_small_file") as mock_upload:
        file_ops._upload_file(str(test_file), "/test.txt", WriteMode.add)
        mock_upload.assert_called_once()


def test_upload_file_large(file_ops, tmp_path):
    """Test upload_file with a large file."""
    large_file = tmp_path / "large.txt"
    large_file.write_bytes(b"0" * (150 * 1024 * 1024 + 1))  # Slightly over 150MB

    with patch.object(file_ops, "_upload_large_file") as mock_upload:
        file_ops._upload_file(str(large_file), "/large.txt", WriteMode.add)
        mock_upload.assert_called_once()


def test_upload_single_file(file_ops, test_file):
    """Test upload of a single file."""
    metadata = FileMetadata(
        name="test.txt",
        path_lower="/test.txt",
        client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
        size=100,
        content_hash="a" * 64,  # Use valid hash length
    )

    with patch.object(file_ops, "_upload_file", return_value=metadata):
        result = file_ops.upload(str(test_file), "/test.txt")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["name"] == "test.txt"


def test_upload_directory(file_ops, tmp_path):
    """Test upload of a directory."""
    # Create test directory structure
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    (test_dir / "file1.txt").write_text("content1")
    (test_dir / "file2.txt").write_text("content2")

    metadata1 = FileMetadata(
        name="file1.txt",
        path_lower="/test_dir/file1.txt",
        client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
        size=100,
        content_hash="a" * 64,  # Use valid hash length
    )
    metadata2 = FileMetadata(
        name="file2.txt",
        path_lower="/test_dir/file2.txt",
        client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
        size=100,
        content_hash="a" * 64,  # Use valid hash length
    )

    with patch.object(
        file_ops,
        "_upload_file",
        side_effect=[metadata1, metadata2],
    ):
        result = file_ops.upload(str(test_dir), "/test_dir")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2


def test_download_file(file_ops, tmp_path, mock_dropbox_client):
    """Test downloading a single file."""
    local_path = tmp_path / "downloaded.txt"
    metadata = FileMetadata(
        name="test.txt",
        path_lower="/test.txt",
        client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
        size=100,
        content_hash="a" * 64,
    )

    mock_response = MagicMock()
    mock_response.iter_content.return_value = [b"test content"]
    mock_dropbox_client.files_download.return_value = (metadata, mock_response)
    mock_dropbox_client.files_get_metadata.return_value = FileMetadata(
        name="test.txt",
        path_lower="/test.txt",
        client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
        size=100,
        content_hash="a" * 64,
    )

    result = file_ops._download_file("/test.txt", str(local_path))
    assert isinstance(result, FileMetadata)
    assert result.name == "test.txt"
    assert local_path.exists()
    assert local_path.read_text() == "test content"


def test_download_large_file(file_ops, tmp_path, mock_dropbox_client):
    """Test downloading a large file."""
    local_path = tmp_path / "downloaded_large.txt"
    metadata = FileMetadata(
        name="large.txt",
        path_lower="/large.txt",
        client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
        size=200 * 1024 * 1024,
        content_hash="a" * 64,
    )

    # Setup mock properly
    mock_dropbox_client.files_get_metadata.return_value = metadata
    mock_dropbox_client.files_download_session_start.return_value = (
        metadata,
        MagicMock(content=b"test content", session_id="test_session"),
    )

    result = file_ops._download_large_file("/large.txt", str(local_path))
    assert isinstance(result, FileMetadata)


def test_download_directory(file_ops, tmp_path, mock_dropbox_client):
    """Test downloading a directory."""
    # Setup mock before any operations
    mock_dropbox_client.files_get_metadata.return_value = FolderMetadata(
        name="test_dir", path_lower="/test_dir", id="id123"
    )
    local_dir = tmp_path / "download_dir"
    metadata1 = FileMetadata(
        name="file1.txt",
        path_lower="/test_dir/file1.txt",
        client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
        size=100,
        content_hash="a" * 64,  # Use valid hash length
    )
    metadata2 = FileMetadata(
        name="file2.txt",
        path_lower="/test_dir/file2.txt",
        client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
        size=100,
        content_hash="a" * 64,  # Use valid hash length
    )

    # Mock list_files to return our test files
    mock_dropbox_client.files_get_metadata = MagicMock(
        return_value=MagicMock(is_file=False)
    )
    file_ops.list_files = MagicMock(
        return_value=pd.DataFrame(
            [
                file_ops._process_metadata(metadata1),
                file_ops._process_metadata(metadata2),
            ]
        )
    )

    # Mock _download_file to simulate file downloads
    file_ops._download_file = MagicMock(side_effect=[metadata1, metadata2])

    mock_dropbox_client.files_get_metadata.return_value = FolderMetadata(
        name="test_dir", path_lower="/test_dir", id="id123"
    )

    result = file_ops.download("/test_dir", str(local_dir))
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2
