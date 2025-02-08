# Nova-PyDropbox

A Python CLI tool for interacting with Dropbox, featuring secure credential management and extensive file operations support.

## Features

- 🔐 Secure credential storage using system keyring or encrypted file fallback
- 🔄 OAuth2 authentication flow with automatic token refresh
- 📁 Comprehensive file operations:
  - File/folder upload with chunked transfer
  - File/folder download with progress tracking
  - List files with filtering options
  - Advanced file operations (move, copy, delete)
- 📊 DataFrame-based file listing results
- 🎯 Hash verification for file integrity
- 📈 Progress tracking for large operations
- 💪 Strong typing and error handling
- 🛡️ Secure token management

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/nova-pydrobox.git
cd nova-pydrobox

# Install using Poetry (recommended)
poetry install

# Or using pip
pip install .
```

## Quick Start

1. First, set up authentication:
```bash
python dropbox_auth.py
```
This will:
- Open the Dropbox App Console in your browser
- Guide you through creating a Dropbox app
- Help you authenticate with your Dropbox account

2. List your files:
```bash
python list_files.py
```

## File Operations

The package provides comprehensive file operations through the `DropboxOperations` class:

- Upload files/folders with progress tracking
- Download files/folders with chunked transfer
- List files with filtering by type and size
- Hash verification for file integrity
- DataFrame-based results for easy analysis

Example filter usage:
```python
filter_criteria = FileFilter(
    file_type=FileType.DOCUMENT,
    min_size=1024,  # 1KB
    max_size=1024*1024,  # 1MB
    recursive=True
)
```

## Security

- Credentials are stored securely using the system keyring when available
- Fallback to encrypted file storage when keyring is not available
- OAuth2 flow with PKCE for enhanced security
- Automatic token refresh handling
- File integrity verification through hashing

## Dependencies

Core:
- dropbox: Dropbox API client
- python-dotenv: Environment variable management
- keyring: Secure credential storage
- cryptography: Encryption for fallback storage
- pandas: Data manipulation and analysis
- tqdm: Progress bar functionality

Optional:
- secretstorage: Linux keyring support
- keyrings-alt: Alternative keyring backends

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
            E --> E2[dropbox_auth.py]
            E --> E3[dropbox_operations.py]
            E --> E4[token_storage.py]
        end

        subgraph Token Storage Operations
            direction TB
            E4 --> T1[TokenStorage Class]
            T1 --> T2[save_tokens]
            T1 --> T3[get_tokens]
            T1 --> T4[clear_tokens]
            T1 --> T5[_test_keyring]
            T1 --> T6[_get_or_create_encryption_key]
        end

        subgraph File Operations
            direction TB
            E3 --> O1[DropboxOperations Class]
            O1 --> O2[upload]
            O1 --> O3[download]
            O1 --> O4[list_files]
            O2 --> O5[_upload_file]
            O2 --> O6[_upload_large_file]
            O3 --> O7[_download_file]
            O3 --> O8[_download_large_file]
        end

        subgraph Authentication Operations
            direction TB
            E2 --> A1[setup_credentials]
            E2 --> A2[authenticate_dropbox]
            E2 --> A3[get_dropbox_client]
            A2 --> T2
            A3 --> T3
        end

        subgraph Dependencies
            direction TB
            P1[dropbox SDK]
            P2[python-dotenv]
            P3[keyring]
            P4[cryptography]
            P5[pandas]
            P6[tqdm]
        end

        E2 --> P1
        E2 --> P2
        E3 --> P1
        E3 --> P5
        E3 --> P6
        E4 --> P3
        E4 --> P4
    end

    %% Style definitions
    classDef default fill:#f9f,stroke:#333,stroke-width:2px
    classDef module fill:#bbf,stroke:#333,stroke-width:2px
    classDef storage fill:#bfb,stroke:#333,stroke-width:2px
    classDef function fill:#dfd,stroke:#333,stroke-width:2px
    classDef dependency fill:#fdd,stroke:#333,stroke-width:2px
    classDef space fill:none,stroke:none

    class A default
    class B,D,E,E1,E2,E3,E4 module
    class T1,O1 storage
    class A1,A2,A3,O2,O3,O4,O5,O6,O7,O8,T2,T3,T4,T5,T6 function
    class P1,P2,P3,P4,P5,P6 dependency
    class space1 space
```

This updated documentation better reflects the current state of the project, including the comprehensive file operations capabilities, enhanced security features, and the addition of progress tracking and data handling features. The architecture diagram now shows the detailed structure of the DropboxOperations class and its relationships with other components.
