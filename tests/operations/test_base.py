"""Tests for the base operations module."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import dropbox
import pandas as pd
import pytest
from dropbox.files import FileMetadata, FolderMetadata, ListFolderResult

from nova_pydrobox.operations.base import BaseOperations, FileFilter


@pytest.fixture
def mock_dropbox_client():
    with patch("nova_pydrobox.auth.authenticator.get_dropbox_client") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def base_ops(mock_dropbox_client):
    """Create BaseOperations instance with mocked client."""
    return BaseOperations(dbx_client=mock_dropbox_client)


def test_init_success(mock_dropbox_client):
    """Test successful initialization of BaseOperations."""
    with patch(
        "nova_pydrobox.operations.base.get_dropbox_client",
        return_value=mock_dropbox_client,
    ):
        ops = BaseOperations()
        assert ops.dbx == mock_dropbox_client
        assert ops.max_workers == 4


def test_init_failure():
    """Test initialization failure when client cannot be created."""
    with patch("nova_pydrobox.operations.base.get_dropbox_client", return_value=None):
        with pytest.raises(ConnectionError):
            BaseOperations()


def test_calculate_file_hash(base_ops, tmp_path):
    """Test file hash calculation."""
    test_file = tmp_path / "test.txt"
    test_content = b"test content"
    test_file.write_bytes(test_content)

    hash_result = base_ops._calculate_file_hash(str(test_file))
    assert isinstance(hash_result, str)
    assert len(hash_result) == 64  # SHA256 hash length


def test_process_metadata_file(base_ops):
    """Test metadata processing for a file."""
    metadata = FileMetadata(
        name="test.txt",
        path_lower="/test.txt",
        client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
        size=100,
        content_hash="a" * 64,  # Valid 64-character hex string
    )

    result = base_ops._process_metadata(metadata)
    assert result == {
        "name": "test.txt",
        "path": "/test.txt",
        "type": "file",
        "size": 100,
        "modified": "2023-01-01T00:00:00Z",
        "hash": "a" * 64,
    }


def test_process_metadata_folder(base_ops):
    """Test metadata processing for a folder."""
    metadata = FolderMetadata(name="test_folder", path_lower="/test_folder")

    result = base_ops._process_metadata(metadata)
    assert result == {
        "name": "test_folder",
        "path": "/test_folder",
        "type": "folder",
        "size": 0,
        "modified": None,
        "hash": None,
    }


def test_process_listing_result(base_ops):
    """Test processing of listing results."""
    entries = [
        FileMetadata(
            name="test.txt",
            path_lower="/test.txt",
            client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
            size=100,
            content_hash="a" * 64,
        ),
        FolderMetadata(name="test_folder", path_lower="/test_folder"),
    ]
    result = ListFolderResult(entries=entries, cursor="cursor123", has_more=False)

    df = base_ops._process_listing_result(result)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert df.iloc[0]["type"] == "file"
    assert df.iloc[1]["type"] == "folder"


def test_list_files_basic(base_ops, mock_dropbox_client):
    """Test basic file listing without filters."""
    entries = [
        FileMetadata(
            name="test.txt",
            path_lower="/test.txt",
            client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
            size=100,
            content_hash="a" * 64,  # 64-char hash required
        )
    ]
    mock_result = ListFolderResult(entries=entries, cursor="cursor123", has_more=False)
    mock_dropbox_client.files_list_folder.return_value = mock_result

    result = base_ops.list_files()
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    mock_dropbox_client.files_list_folder.assert_called_once_with("", recursive=False)


def test_list_files_with_filter(base_ops, mock_dropbox_client):
    """Test file listing with filters."""
    entries = [
        FileMetadata(
            name="test.txt",
            path_lower="/test.txt",
            client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
            size=100,
            content_hash="a" * 64,
        ),
        FileMetadata(
            name="big.txt",
            path_lower="/big.txt",
            client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
            size=1000,
            content_hash="a" * 64,
        ),
    ]
    mock_result = ListFolderResult(entries=entries, cursor="cursor123", has_more=False)
    mock_dropbox_client.files_list_folder.return_value = mock_result

    # Simplify filter criteria for testing
    filter_criteria = FileFilter(min_size=500)
    result = base_ops.list_files(filter_criteria=filter_criteria)
    assert len(result) == 1


def test_list_files_pagination(base_ops, mock_dropbox_client):
    """Test file listing with pagination."""
    entries1 = [
        FileMetadata(
            name="test1.txt",
            path_lower="/test1.txt",
            client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
            size=100,
            content_hash="a" * 64,
        )
    ]
    entries2 = [
        FileMetadata(
            name="test2.txt",
            path_lower="/test2.txt",
            client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
            size=200,
            content_hash="a" * 64,
        )
    ]

    result1 = ListFolderResult(entries=entries1, cursor="cursor123", has_more=True)
    result2 = ListFolderResult(entries=entries2, cursor="cursor456", has_more=False)

    mock_dropbox_client.files_list_folder.return_value = result1
    mock_dropbox_client.files_list_folder_continue.return_value = result2

    result = base_ops.list_files()
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2
    assert result.iloc[0]["name"] == "test1.txt"
    assert result.iloc[1]["name"] == "test2.txt"


def test_list_files_api_error(base_ops, mock_dropbox_client):
    """Test file listing with API error."""
    mock_dropbox_client.files_list_folder.side_effect = dropbox.exceptions.ApiError(
        request_id="test_id",
        error="test_error",
        user_message_text="Test error message",
        user_message_locale="en",
    )

    with pytest.raises(dropbox.exceptions.ApiError):
        base_ops.list_files()


def test_delete(base_ops, mock_dropbox_client):
    """Test delete operation."""
    mock_dropbox_client.files_delete_v2.return_value = MagicMock()

    result = base_ops.delete("/test.txt")
    assert result is True
    mock_dropbox_client.files_delete_v2.assert_called_once_with("/test.txt")


def test_move(base_ops, mock_dropbox_client):
    """Test move operation."""
    metadata = FileMetadata(
        name="test.txt",
        path_lower="/new/test.txt",
        client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
        size=100,
        content_hash="a" * 64,
    )
    mock_dropbox_client.files_move_v2.return_value = MagicMock(metadata=metadata)

    result = base_ops.move("/test.txt", "/new/test.txt")
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert result.iloc[0]["path"] == "/new/test.txt"


def test_copy(base_ops, mock_dropbox_client):
    """Test copy operation."""
    metadata = FileMetadata(
        name="test.txt",
        path_lower="/new/test.txt",
        client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
        size=100,
        content_hash="a" * 64,
    )
    mock_dropbox_client.files_copy_v2.return_value = MagicMock(metadata=metadata)

    result = base_ops.copy("/test.txt", "/new/test.txt")
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert result.iloc[0]["path"] == "/new/test.txt"


def test_rename(base_ops, mock_dropbox_client):
    """Test rename operation."""
    metadata = FileMetadata(
        name="new.txt",
        path_lower="/new.txt",
        client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
        size=100,
        content_hash="a" * 64,
    )
    mock_dropbox_client.files_move_v2.return_value = MagicMock(metadata=metadata)

    result = base_ops.rename("/test.txt", "new.txt")
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert result.iloc[0]["name"] == "new.txt"


def test_search(base_ops, mock_dropbox_client):
    """Test search operation."""
    metadata = FileMetadata(
        name="test.txt",
        path_lower="/test.txt",
        client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
        size=100,
        content_hash="a" * 64,
    )
    match = MagicMock(metadata=metadata)
    mock_result = MagicMock(matches=[match], has_more=False)
    mock_dropbox_client.files_search_v2.return_value = mock_result

    result = base_ops.search("test")
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert result.iloc[0]["name"] == "test.txt"
