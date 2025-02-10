class NovaDropboxError(Exception):
    """Base exception for all Nova-PyDropbox errors"""

    pass


class AuthenticationError(NovaDropboxError):
    """Raised when authentication fails"""

    pass


class TokenStorageError(NovaDropboxError):
    """Raised when there are issues with token storage"""

    pass


class OperationError(NovaDropboxError):
    """Base class for operation-related errors"""

    pass


class UploadError(OperationError):
    """Raised when file upload fails"""

    pass


class DownloadError(OperationError):
    """Raised when file download fails"""

    pass


class ConfigurationError(NovaDropboxError):
    """Raised when there are configuration issues"""

    pass


class ValidationError(NovaDropboxError):
    """Raised when validation fails"""

    pass


class ConnectionError(NovaDropboxError):
    """Raised when connection to Dropbox fails"""

    pass
