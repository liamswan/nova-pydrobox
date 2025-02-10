"""Tests for the folder operations module."""

from datetime import datetime, timezone
from typing import Generator
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from dropbox import Dropbox
from dropbox.files import FileMetadata, FolderMetadata

from nova_pydrobox.operations.folders import FolderOperations


@pytest.fixture
def mock_dropbox_client() -> Generator[MagicMock, None, None]:
    """Create a mock Dropbox client."""
    client = MagicMock(spec=Dropbox)
    yield client


@pytest.fixture
def folder_ops(mock_dropbox_client: MagicMock) -> FolderOperations:
    """Create a FolderOperations instance with mock client."""
    return FolderOperations(dbx_client=mock_dropbox_client)


def test_create_folder(
    folder_ops: FolderOperations, mock_dropbox_client: MagicMock
) -> None:
    """Test folder creation."""
    # Setup mock metadata
    metadata = FolderMetadata(name="test_folder", path_lower="/test_folder", id="id123")

    # Setup mock response
    mock_response = MagicMock()
    mock_response.metadata = metadata
    mock_dropbox_client.files_create_folder_v2.return_value = mock_response

    # Execute test
    result = folder_ops.create_folder("/test_folder")

    # Assertions
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert result.iloc[0]["name"] == "test_folder"
    assert result.iloc[0]["type"] == "folder"
    mock_dropbox_client.files_create_folder_v2.assert_called_once_with("/test_folder")


def test_get_folder_size(folder_ops: FolderOperations) -> None:
    """Test getting folder size."""
    mock_files = pd.DataFrame(
        [
            {
                "name": "file1.txt",
                "path": "/test_folder/file1.txt",
                "type": "file",
                "size": 100,
            },
            {
                "name": "file2.txt",
                "path": "/test_folder/file2.txt",
                "type": "file",
                "size": 200,
            },
        ]
    )

    with patch.object(folder_ops, "list_files", return_value=mock_files):
        size = folder_ops.get_folder_size("/test_folder")
        assert size == 300


def test_get_folder_structure(folder_ops: FolderOperations) -> None:
    """Test getting folder structure."""
    mock_files = pd.DataFrame(
        [
            {
                "name": "file1.txt",
                "path": "/test_folder/file1.txt",
                "type": "file",
                "size": 100,
            },
            {
                "name": "subfolder",
                "path": "/test_folder/subfolder",
                "type": "folder",
                "size": 0,
            },
        ]
    )

    with patch.object(folder_ops, "list_files", return_value=mock_files):
        result = folder_ops.get_folder_structure("/test_folder")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert result.iloc[0]["type"] == "file"
        assert result.iloc[1]["type"] == "folder"


def test_is_empty_true(folder_ops: FolderOperations) -> None:
    """Test checking if folder is empty (true case)."""
    with patch.object(folder_ops, "list_files", return_value=pd.DataFrame()):
        assert folder_ops.is_empty("/test_folder") is True


def test_is_empty_false(folder_ops: FolderOperations) -> None:
    """Test checking if folder is empty (false case)."""
    mock_files = pd.DataFrame(
        [
            {
                "name": "file1.txt",
                "path": "/test_folder/file1.txt",
                "type": "file",
                "size": 100,
            }
        ]
    )

    with patch.object(folder_ops, "list_files", return_value=mock_files):
        assert folder_ops.is_empty("/test_folder") is False


def test_get_folder_metadata(
    folder_ops: FolderOperations, mock_dropbox_client: MagicMock
) -> None:
    """Test getting folder metadata."""
    metadata = FolderMetadata(name="test_folder", path_lower="/test_folder", id="id123")
    mock_dropbox_client.files_get_metadata.return_value = metadata

    result = folder_ops.get_folder_metadata("/test_folder")
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert result.iloc[0]["name"] == "test_folder"
    assert result.iloc[0]["type"] == "folder"


def test_get_folder_metadata_not_folder(
    folder_ops: FolderOperations, mock_dropbox_client: MagicMock
) -> None:
    """Test getting folder metadata for a file (should fail)."""
    content_hash = "a" * 64
    metadata = FileMetadata(
        name="test.txt",
        path_lower="/test.txt",
        client_modified=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
        size=100,
        content_hash=content_hash,
    )
    mock_dropbox_client.files_get_metadata.return_value = metadata

    with pytest.raises(ValueError, match="/test.txt is not a folder"):
        folder_ops.get_folder_metadata("/test.txt")
