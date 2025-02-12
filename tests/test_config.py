"""Tests for the config module."""

import pytest

from nova_pydrobox.config import Config


def test_config_default_values():
    """Test that Config initializes with correct default values."""
    config = Config()
    assert config.CHUNK_SIZE == 4 * 1024 * 1024  # 4MB
    assert config.LARGE_FILE_THRESHOLD == 150 * 1024 * 1024  # 150MB
    assert config.SERVICE_NAME == "nova-pydrobox"
    assert config.TOKEN_ENCRYPTION_ALGORITHM == "fernet"
    assert config.MAX_RETRIES == 3
    assert config.TIMEOUT == 30
    assert config.PROGRESS_BAR_UNIT == "B"
    assert config.PROGRESS_BAR_UNIT_SCALE is True


def test_config_custom_values():
    """Test that Config accepts custom values."""
    config = Config(
        CHUNK_SIZE=8 * 1024 * 1024,  # 8MB
        LARGE_FILE_THRESHOLD=200 * 1024 * 1024,  # 200MB
        SERVICE_NAME="custom-service",
        TOKEN_ENCRYPTION_ALGORITHM="custom-algo",
        MAX_RETRIES=5,
        TIMEOUT=60,
        PROGRESS_BAR_UNIT="MB",
        PROGRESS_BAR_UNIT_SCALE=False,
    )
    assert config.CHUNK_SIZE == 8 * 1024 * 1024
    assert config.LARGE_FILE_THRESHOLD == 200 * 1024 * 1024
    assert config.SERVICE_NAME == "custom-service"
    assert config.TOKEN_ENCRYPTION_ALGORITHM == "custom-algo"
    assert config.MAX_RETRIES == 5
    assert config.TIMEOUT == 60
    assert config.PROGRESS_BAR_UNIT == "MB"
    assert config.PROGRESS_BAR_UNIT_SCALE is False


def test_chunk_size_validation():
    """Test that Config raises ValueError for invalid CHUNK_SIZE."""
    with pytest.raises(ValueError, match="CHUNK_SIZE must be positive"):
        Config(CHUNK_SIZE=0)
    
    with pytest.raises(ValueError, match="CHUNK_SIZE must be positive"):
        Config(CHUNK_SIZE=-1024)
