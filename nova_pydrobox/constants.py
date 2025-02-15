"""
Constants module for nova-pydrobox.

This module defines enumerations and constant values used throughout the package:
- File type classifications
- Operation modes and statuses
- Authorization scopes
- Standard API messages

Note:
    All enumerations inherit from Enum for type safety and consistency.
"""

from enum import Enum, auto
from typing import Dict


class FileType(Enum):
    """
    Supported file types for filtering operations.

    Attributes:
        ALL: All file types (no filtering)
        DOCUMENT: Document files (e.g., .pdf, .doc, .txt)
        FOLDER: Directory/folder objects
        IMAGE: Image files (e.g., .jpg, .png, .gif)
        VIDEO: Video files (e.g., .mp4, .mov)
        AUDIO: Audio files (e.g., .mp3, .wav)

    Example:
        ```python
        # Filter for image files
        file_filter = FileFilter(file_type=FileType.IMAGE)
        ```
    """

    ALL = "all"
    DOCUMENT = "document"
    FOLDER = "folder"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class WriteMode(Enum):
    """
    File write modes for upload operations.

    Attributes:
        ADD: Add new file, fail if exists
        OVERWRITE: Overwrite existing file

    Example:
        ```python
        # Upload with overwrite
        ops.upload("file.txt", "/path", mode=WriteMode.OVERWRITE)
        ```
    """

    ADD = "add"
    OVERWRITE = "overwrite"


class AuthScope(Enum):
    """
    Authorization scopes for Dropbox API access.

    Attributes:
        FULL_DROPBOX: Full Dropbox access
        APP_FOLDER: Limited to app folder only

    Note:
        APP_FOLDER is more restrictive but safer for basic operations
    """

    FULL_DROPBOX = "full_dropbox"
    APP_FOLDER = "app_folder"


class OperationStatus(Enum):
    """
    Operation status indicators for async operations.

    Attributes:
        SUCCESS: Operation completed successfully
        FAILED: Operation failed
        IN_PROGRESS: Operation is still running

    Note:
        Uses auto() for automatic value assignment
    """

    SUCCESS = auto()
    FAILED = auto()
    IN_PROGRESS = auto()


# API response messages
API_MESSAGES: Dict[str, str] = {
    "auth_success": "Authentication successful! Tokens securely stored.",
    "auth_failed": "Authentication failed: {}",
    "token_error": "Error saving tokens.",
    "connection_error": "Could not initialize Dropbox client",
    "upload_error": "Error uploading: {}",
    "download_error": "Error downloading: {}",
}

# Type hint and documentation for API_MESSAGES
"""
Standard API response messages.

Keys:
    auth_success (str): Successful authentication message
    auth_failed (str): Authentication failure message template
    token_error (str): Token storage error message
    connection_error (str): Client initialization error message
    upload_error (str): Upload error message template
    download_error (str): Download error message template

Note:
    Messages with {} support string formatting for error details
"""
