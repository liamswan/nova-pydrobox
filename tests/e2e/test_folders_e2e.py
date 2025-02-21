"""End-to-end tests for folder operations."""
import time

import pandas as pd
import pytest
from dropbox.exceptions import ApiError

from nova_pydrobox.operations.files import FileOperations
from nova_pydrobox.operations.folders import FolderOperations

@pytest.mark.e2e
def test_folder_creation_and_metadata(e2e_auth, e2e_dropbox_client, e2e_test_path):
    """
    Test folder creation and metadata retrieval.
    
    This test:
    1. Creates a new folder
    2. Verifies folder metadata
    3. Tests duplicate creation handling
    4. Verifies empty folder detection
    """
    folder_ops = FolderOperations(dbx_client=e2e_dropbox_client)
    test_folder_path = f"{e2e_test_path}/test_folder"
    
    # Test folder creation
    result = folder_ops.create_folder(test_folder_path)
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert result.iloc[0]["path"].lower() == test_folder_path.lower()
    assert result.iloc[0]["type"] == "folder"
    
    # Test duplicate creation
    duplicate_result = folder_ops.create_folder(test_folder_path)
    assert isinstance(duplicate_result, pd.DataFrame)
    assert len(duplicate_result) == 1
    assert duplicate_result.iloc[0]["path"].lower() == test_folder_path.lower()
    
    # Test metadata retrieval
    metadata = folder_ops.get_folder_metadata(test_folder_path)
    assert isinstance(metadata, pd.DataFrame)
    assert len(metadata) == 1
    assert metadata.iloc[0]["path"].lower() == test_folder_path.lower()
    
    # Test empty folder detection
    assert folder_ops.is_empty(test_folder_path)

@pytest.mark.e2e
def test_folder_structure_and_size(
    e2e_auth, e2e_dropbox_client, test_folder, e2e_test_path
):
    """
    Test folder structure analysis and size calculations.
    
    This test:
    1. Creates a nested folder structure
    2. Uploads test files
    3. Verifies structure information
    4. Checks size calculations
    """
    file_ops = FileOperations(dbx_client=e2e_dropbox_client)
    folder_ops = FolderOperations(dbx_client=e2e_dropbox_client)
    
    # Upload test folder
    test_dropbox_path = f"{e2e_test_path}/folder_structure_test"
    file_ops.upload(str(test_folder), test_dropbox_path)
    
    # Allow some time for changes to propagate
    time.sleep(2)
    
    # Test folder structure
    structure = folder_ops.get_folder_structure(test_dropbox_path)
    assert isinstance(structure, pd.DataFrame)
    assert len(structure) >= 4  # main folder + 3 files + subfolder
    
    # Verify structure contains expected paths
    paths = set(structure["path"].str.lower())
    assert f"{test_dropbox_path}/file1.txt".lower() in paths
    assert f"{test_dropbox_path}/file2.txt".lower() in paths
    assert f"{test_dropbox_path}/subfolder/file3.txt".lower() in paths
    
    # Test folder size
    total_size = folder_ops.get_folder_size(test_dropbox_path)
    assert total_size > 0
    assert total_size == structure["size"].sum()

@pytest.mark.e2e
def test_nested_folder_operations(e2e_auth, e2e_dropbox_client, e2e_test_path):
    """
    Test operations with deeply nested folders.
    
    This test:
    1. Creates a deep folder structure
    2. Verifies creation at each level
    3. Tests metadata and size calculations
    4. Verifies empty status of nested folders
    """
    folder_ops = FolderOperations(dbx_client=e2e_dropbox_client)
    base_path = f"{e2e_test_path}/nested_test"
    
    # Create nested structure
    paths = []
    current_path = base_path
    for i in range(5):  # Create 5 levels deep
        paths.append(current_path)
        result = folder_ops.create_folder(current_path)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["path"].lower() == current_path.lower()
        current_path = f"{current_path}/level_{i+1}"
    
    # Verify structure
    structure = folder_ops.get_folder_structure(base_path)
    assert isinstance(structure, pd.DataFrame)
    assert len(structure) >= 5  # At least 5 folders
    
    # Check empty status of all folders
    for path in paths:
        assert folder_ops.is_empty(path) == (path == current_path)

@pytest.mark.e2e
def test_folder_error_handling(e2e_auth, e2e_dropbox_client, e2e_test_path):
    """
    Test error handling in folder operations.
    
    This test:
    1. Tests invalid path handling
    2. Tests non-existent folder operations
    3. Verifies error reporting
    """
    folder_ops = FolderOperations(dbx_client=e2e_dropbox_client)
    
    # Test invalid characters in path
    with pytest.raises(ApiError):
        folder_ops.create_folder(f"{e2e_test_path}/invalid*folder")
    
    # Test operations on non-existent folder
    with pytest.raises(ApiError):
        folder_ops.get_folder_metadata(f"{e2e_test_path}/nonexistent")
    
    with pytest.raises(ApiError):
        folder_ops.get_folder_size(f"{e2e_test_path}/nonexistent")

    with pytest.raises(ApiError):
        folder_ops.is_empty(f"{e2e_test_path}/nonexistent")

@pytest.mark.e2e
def test_concurrent_folder_creation(e2e_auth, e2e_dropbox_client, e2e_test_path):
    """
    Test concurrent folder operations.
    
    This test:
    1. Creates multiple folders rapidly
    2. Verifies all were created correctly
    3. Tests structure integrity
    """
    folder_ops = FolderOperations(dbx_client=e2e_dropbox_client)
    base_path = f"{e2e_test_path}/concurrent_test"
    
    # Create multiple folders quickly
    folders = []
    for i in range(5):
        folder_path = f"{base_path}/folder_{i}"
        result = folder_ops.create_folder(folder_path)
        folders.append(folder_path)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
    
    # Verify all folders exist
    structure = folder_ops.get_folder_structure(base_path)
    created_paths = set(structure["path"].str.lower())
    for folder in folders:
        assert folder.lower() in created_paths
