"""Configuration and fixtures for E2E tests."""
import logging
import os
import time
import uuid
from pathlib import Path

import pytest

from nova_pydrobox.auth.authenticator import get_dropbox_client
from tests.e2e.utils.test_auth import E2ETestAuthenticator

logger = logging.getLogger(__name__)

def pytest_addoption(parser):
    """Add E2E test options to pytest."""
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="run end-to-end tests"
    )

def pytest_configure(config):
    """Register e2e marker."""
    config.addinivalue_line(
        "markers",
        "e2e: mark test as end-to-end test"
    )

def pytest_collection_modifyitems(config, items):
    """Skip E2E tests unless --run-e2e option is provided."""
    if not config.getoption("--run-e2e"):
        skip_e2e = pytest.mark.skip(reason="need --run-e2e option to run")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e)

@pytest.fixture(scope="session")
def e2e_auth():
    """
    Create E2E test authenticator with test credentials.
    
    Requires environment variables:
    - DROPBOX_TEST_APP_KEY
    - DROPBOX_TEST_APP_SECRET
    - DROPBOX_TEST_REFRESH_TOKEN
    """
    required_vars = [
        "DROPBOX_TEST_APP_KEY",
        "DROPBOX_TEST_APP_SECRET",
        "DROPBOX_TEST_REFRESH_TOKEN"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        pytest.skip("Missing required environment variables: {}".format(", ".join(missing_vars)))
    
    auth = E2ETestAuthenticator(
        test_app_key=os.getenv("DROPBOX_TEST_APP_KEY"),
        test_app_secret=os.getenv("DROPBOX_TEST_APP_SECRET"),
        test_refresh_token=os.getenv("DROPBOX_TEST_REFRESH_TOKEN")
    )
    
    if not auth.authenticate_dropbox():
        pytest.skip("Failed to authenticate with test credentials")
    
    return auth

@pytest.fixture(scope="session")
def e2e_dropbox_client(e2e_auth):
    """Get authenticated Dropbox client for E2E tests."""
    client = get_dropbox_client()
    if not client:
        pytest.skip("Failed to create Dropbox client")
    return client

@pytest.fixture(scope="function")
def test_file(tmp_path: Path):
    """Create a temporary test file."""
    content = "Test content {}".format(uuid.uuid4())
    file_path = tmp_path / "test_file.txt"  # Path operation
    file_path.write_text(content)
    return file_path

@pytest.fixture(scope="function")
def test_folder(tmp_path: Path):
    """
    Create a temporary test folder with files.
    
    Args:
        tmp_path: Pytest fixture providing temporary directory Path
        
    Returns:
        Path: Directory containing test files and folders
    """
    # Create test folder structure
    folder = tmp_path / "test_folder"  # Path operation
    folder.mkdir()
    
    # Create test files
    (folder / "file1.txt").write_text("Content 1")
    (folder / "file2.txt").write_text("Content 2")
    subfolder = folder / "subfolder"  # Path operation
    subfolder.mkdir()
    (subfolder / "file3.txt").write_text("Content 3")
    
    return folder

@pytest.fixture(scope="function")
def e2e_test_path():
    """
    Get a unique test path in Dropbox for isolation.
    
    Returns a path like: /e2e_tests/{timestamp}_{uuid}/
    This ensures each test run has its own isolated workspace.
    """
    base_path = "/e2e_tests"
    test_id = "{}_{:.8}".format(int(time.time()), uuid.uuid4().hex)
    return "{}/{}".format(base_path, test_id)

@pytest.fixture(scope="function", autouse=True)
def cleanup_test_path(e2e_dropbox_client, e2e_test_path):
    """
    Automatically clean up test files after each test.
    
    This fixture runs automatically for all E2E tests to ensure
    we don't leave test data in the Dropbox account.
    """
    yield  # Let the test run
    
    try:
        e2e_dropbox_client.files_delete_v2(e2e_test_path)
        logger.info("Cleaned up test path: {}".format(e2e_test_path))
    except Exception as e:
        logger.warning("Failed to clean up test path {}: {}".format(e2e_test_path, e))
