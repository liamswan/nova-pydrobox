# Nova-PyDropbox

[![Build status](https://github.com/liamswan/nova-pydrobox/workflows/CI/badge.svg)](https://github.com/yourusername/nova-pydrobox/actions)
[![codecov](https://codecov.io/gh/liamswan/nova-pydrobox/graph/badge.svg?token=ESQNIHM4QY)](https://codecov.io/gh/liamswan/nova-pydrobox)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A Python library providing an enhanced wrapper around the [Dropbox Python SDK](https://github.com/dropbox/dropbox-sdk-python), featuring secure authentication, comprehensive file operations, and progress tracking.

## Features

- 🔐 Secure Authentication
  - OAuth2 implementation using official Dropbox SDK
  - System keyring integration with encrypted file fallback
  - Automatic token refresh handling
  
- 📁 Enhanced File Operations
  - Simplified high-level API around Dropbox SDK core methods
  - Smart chunked upload/download (auto-switches based on file size)
  - Automatic retry handling and error management
  - Progress tracking with tqdm integration
  
- 📊 Advanced Features
  - Pandas DataFrame responses for easy data manipulation
  - Built-in file hash verification
  - Automatic chunking for large files (>150MB)
  - Recursive directory operations

- 🔍 Structured File Management
  - Typed file operations (Documents, Images, Videos, Audio)
  - Advanced search with filters
  - Folder size calculations
  - Empty folder detection

## Quick Start

```python
from nova_pydrobox import Authenticator, FileOperations, FolderOperations

# First-time setup
auth = Authenticator()
auth.authenticate_dropbox()

# Initialize operations
files = FileOperations()
folders = FolderOperations()

# Upload with progress bar
result = files.upload('local_file.txt', '/remote_file.txt')
print(f"Upload result: {result}")

# Download with automatic chunking
result = files.download('/remote_file.txt', 'local_download.txt')

# List files with pandas DataFrame output
files = folders.list_files("/my_folder")
print(files[['name', 'size', 'modified']])
```

## Key Differences from Official SDK

Nova-PyDropbox enhances the official Dropbox SDK by providing:

1. **Simplified API**
   - High-level operations that handle common use cases
   - Automatic handling of chunked transfers
   - Progress bars for long operations

2. **Data Science Integration**
   - Pandas DataFrame responses
   - Structured data filtering
   - Size and modification tracking

3. **Enhanced Security**
   - Keyring-based token storage
   - Encrypted fallback storage
   - Automatic token refresh


## Core Dependencies

- `dropbox`: Dropbox API client
- `python-dotenv`: Environment variable management
- `keyring`: Secure credential storage
- `cryptography`: Encryption for fallback storage
- `pandas`: Data manipulation
- `tqdm`: Progress tracking

## Development

This project uses Poetry for dependency management and builds:

```bash
# Install with development dependencies
poetry install --with dev

# Run tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=nova_pydrobox tests/ --cov-report=xml
```

## Python Version Support

Tested on Python versions:
- 3.8
- 3.9
- 3.10
- 3.11
- 3.12
- 3.13

## CI/CD

- Automated testing on Ubuntu, Windows, and macOS
- Code coverage tracking with Codecov
- Automated dependency updates

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Architecture

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'fontSize': '16px' }}}%%
graph TB
    space1[ ]
    space1 --- Nova-PyDropbox

    subgraph Nova-PyDropbox["Nova-PyDropbox Application"]
        subgraph Project Structure
            direction TB
            A[Project Root]
            A --> B[pyproject.toml]
            A --> D[tests/]
            A --> E[nova_pydrobox/]

            E --> E1[__init__.py]
            E --> Auth[auth/]
            E --> Ops[operations/]
            E --> Utils[utils/]
            E --> Config[config.py]
            E --> Constants[constants.py]
            E --> Types[types.py]
            E --> Exceptions[exceptions.py]

            Auth --> A1[authenticator.py]
            Auth --> A2[token_storage.py]
            Ops --> O1[operations.py]
        end

        subgraph Authentication Flow
            direction TB
            A1 --> AF1[setup_credentials]
            A1 --> AF2[authenticate_dropbox]
            A1 --> AF3[get_dropbox_client]
            A2 --> TS1[TokenStorage]
            TS1 --> TS2[save_tokens]
            TS1 --> TS3[get_tokens]
            TS1 --> TS4[clear_tokens]
        end

        subgraph File Operations
            direction TB
            O1 --> FO1[DropboxOperations]
            FO1 --> FO2[sync_methods]
            FO1 --> FO3[async_methods]

            FO2 --> Sync1[upload]
            FO2 --> Sync2[download]
            FO2 --> Sync3[list_files]
            FO2 --> Sync4[search]

            FO3 --> Async1[upload_async]
            FO3 --> Async2[download_async]

            FO1 --> Helper1[_process_metadata]
            FO1 --> Helper2[_calculate_hash]
        end

        subgraph Dependencies
            direction TB
            P1[dropbox SDK]
            P2[python-dotenv]
            P3[keyring]
            P4[cryptography]
            P5[pandas]
            P6[tqdm]
            P7[pytest]
            P8[pytest-asyncio]
        end

        %% Dependency connections
        Auth --> P1
        Auth --> P2
        Auth --> P3
        A2 --> P4
        Ops --> P1
        Ops --> P5
        Ops --> P6
        D --> P7
        D --> P8
    end

    %% Style definitions
    classDef default fill:#f9f,stroke:#333,stroke-width:2px
    classDef module fill:#bbf,stroke:#333,stroke-width:2px
    classDef storage fill:#bfb,stroke:#333,stroke-width:2px
    classDef function fill:#dfd,stroke:#333,stroke-width:2px
    classDef dependency fill:#fdd,stroke:#333,stroke-width:2px
    classDef space fill:none,stroke:none

    class A default
    class B,D,E,E1,Auth,Ops,Utils,Config,Constants,Types,Exceptions module
    class TS1 storage
    class AF1,AF2,AF3,TS2,TS3,TS4,FO2,FO3,Helper1,Helper2 function
    class P1,P2,P3,P4,P5,P6,P7,P8 dependency
    class space1 space
```

### Key Architecture Components

1. **Project Structure**
   - Modular organization with clear separation of concerns
   - Core utilities and configurations centralized
   - Type definitions and constants isolated

2. **Authentication Flow**
   - Token management with system keyring integration
   - OAuth2 implementation
   - Secure fallback storage mechanisms

3. **File Operations**
   - File and folder operations
   - Progress tracking integration
   - Hash verification for integrity checks

4. **Dependencies**
   - Core API integration (dropbox)
   - Security components (keyring, cryptography)
   - Utility libraries (pandas, tqdm)
   - Testing framework (pytest)

The architecture emphasizes:
- Clear separation of concerns
- Secure credential management
- Efficient file handling
- Comprehensive testing support

## License

Distributed under the MIT License. See `LICENSE` for more information.
    class P1,P2,P3,P4,P5,P6,P7,P8 dependency
    class space1 space
```

### Key Architecture Components

1. **Project Structure**
   - Modular organization with clear separation of concerns
   - Core utilities and configurations centralized
   - Type definitions and constants isolated

2. **Authentication Flow**
   - Token management with system keyring integration
   - OAuth2 implementation
   - Secure fallback storage mechanisms

3. **File Operations**
   - File and folder operations
   - Progress tracking integration
   - Hash verification for integrity checks

4. **Dependencies**
   - Core API integration (dropbox)
   - Security components (keyring, cryptography)
   - Utility libraries (pandas, tqdm)
   - Testing framework (pytest)

The architecture emphasizes:
- Clear separation of concerns
- Secure credential management
- Efficient file handling
- Comprehensive testing support

## License

Distributed under the MIT License. See `LICENSE` for more information.
