# End-to-End Testing for nova-pydrobox

This directory contains end-to-end tests that verify nova-pydrobox's functionality by interacting with the real Dropbox API.

## Setup

1. Create a test Dropbox app for testing:
   - Go to https://www.dropbox.com/developers/apps
   - Click "Create app"
   - Choose "Scoped access"
   - Choose access type (Full Dropbox recommended for testing)
   - Give it a unique name like "nova-pydrobox-testing"

2. Configure test environment variables:
   ```bash
   export DROPBOX_TEST_APP_KEY="your_test_app_key"
   export DROPBOX_TEST_APP_SECRET="your_test_app_secret"
   export DROPBOX_TEST_REFRESH_TOKEN="your_test_refresh_token"
   ```

   To get the refresh token:
   1. Go to your test app's settings
   2. Under "OAuth 2", find "Generated access token"
   3. Click "Generate" to create a token
   4. This will be your refresh token

## Running Tests

E2E tests are marked with the `@pytest.mark.e2e` decorator and are skipped by default. To run them:

Run only E2E tests:
```bash
pytest -v -m e2e
```

Run E2E tests along with other tests:
```bash
pytest -v --run-e2e
```

## Test Organization

- `conftest.py`: Test fixtures and configuration
- `utils/test_auth.py`: E2E test authentication handling
- `test_files_e2e.py`: File operation tests
- `test_folders_e2e.py`: Folder operation tests
- `test_cli_e2e.py`: Command-line interface tests
- `test_auth_flow_e2e.py`: Authentication flow tests
- `test_performance_e2e.py`: Performance and resource usage tests

## Test Design

The E2E tests:
- Use a real Dropbox account
- Create isolated test directories
- Clean up after themselves
- Run against the actual API
- Test complete operation cycles

## Adding New Tests

1. Create a new test file prefixed with `test_` and suffixed with `_e2e.py`
2. Use the `@pytest.mark.e2e` decorator
3. Use the provided fixtures:
   - `e2e_auth`: Authenticated test instance
   - `e2e_dropbox_client`: Dropbox client
   - `e2e_test_path`: Unique test directory path
   - `test_file`: Sample test file
   - `test_folder`: Sample test folder structure

## CI/CD Integration

For GitHub Actions:

```yaml
name: E2E Tests

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    env:
      DROPBOX_TEST_APP_KEY: ${{ secrets.DROPBOX_TEST_APP_KEY }}
      DROPBOX_TEST_APP_SECRET: ${{ secrets.DROPBOX_TEST_APP_SECRET }}
      DROPBOX_TEST_REFRESH_TOKEN: ${{ secrets.DROPBOX_TEST_REFRESH_TOKEN }}
    
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.10'
    - name: Install dependencies
      run: python -m pip install --upgrade pip && pip install poetry && poetry install
    - name: Run E2E tests
      run: poetry run pytest -v -m e2e
