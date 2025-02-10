from enum import Enum, auto
from typing import Dict


class FileType(Enum):
    """Supported file types for filtering"""

    ALL = "all"
    DOCUMENT = "document"
    FOLDER = "folder"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class WriteMode(Enum):
    """File write modes"""

    ADD = "add"
    OVERWRITE = "overwrite"


class AuthScope(Enum):
    """Authorization scopes"""

    FULL_DROPBOX = "full_dropbox"
    APP_FOLDER = "app_folder"


class OperationStatus(Enum):
    """Operation status indicators"""

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
