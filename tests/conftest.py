import pytest
from dropbox.files import FileMetadata


@pytest.fixture
def mock_dbx(mocker):
    mock = mocker.patch("dropbox.Dropbox", spec=True)
    dbx = mock.return_value
    # Setup common mock responses
    dbx.files_upload.return_value = FileMetadata(
        name="test.txt", path_display="/test.txt", size=1024
    )
    return dbx


@pytest.fixture
def mock_token_storage(mocker):
    # Mock the keyring operations
    mocker.patch("keyring.get_password", return_value="test_password")
    mocker.patch("keyring.set_password")

    mock = mocker.patch("nova_pydrobox.token_storage.TokenStorage")
    storage = mock.return_value
    storage.get_tokens.return_value = {
        "app_key": "test_key",
        "app_secret": "test_secret",
        "refresh_token": "test_refresh",
    }
    return storage


@pytest.fixture
def temp_test_files(tmp_path):
    # Create test files/folders structure
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    return tmp_path
