from dataclasses import dataclass


@dataclass
class Config:
    """Global configuration settings for Nova-PyDropbox"""

    # File operation settings
    CHUNK_SIZE: int = 4 * 1024 * 1024  # 4MB chunks for file operations
    LARGE_FILE_THRESHOLD: int = 150 * 1024 * 1024  # 150MB threshold for large files

    # Authentication settings
    SERVICE_NAME: str = "nova-pydrobox"
    TOKEN_ENCRYPTION_ALGORITHM: str = "fernet"

    # API settings
    MAX_RETRIES: int = 3
    TIMEOUT: int = 30

    # Progress bar settings
    PROGRESS_BAR_UNIT: str = "B"
    PROGRESS_BAR_UNIT_SCALE: bool = True

    def __post_init__(self):
        """Validate configuration after initialization"""
        if self.CHUNK_SIZE <= 0:
            raise ValueError("CHUNK_SIZE must be positive")
