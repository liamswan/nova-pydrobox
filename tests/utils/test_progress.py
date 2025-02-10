"""Tests for the progress utilities module."""

import pytest
from tqdm import tqdm

from nova_pydrobox.utils.progress import create_progress_bar, estimate_time, format_size


def test_create_progress_bar():
    """Test progress bar creation with default parameters."""
    progress_bar = create_progress_bar(total=100)
    assert isinstance(progress_bar, tqdm)
    assert progress_bar.total == 100
    assert progress_bar.unit == "B"
    assert progress_bar.unit_scale is True
    progress_bar.close()


def test_create_progress_bar_custom_params():
    """Test progress bar creation with custom parameters."""
    progress_bar = create_progress_bar(
        total=1000,
        desc="Uploading",
        unit="KB",
        unit_scale=False,
        unit_divisor=1000,
        disable=True,
        leave=False,
        initial=10,
        miniters=2,
        dynamic_ncols=False,
    )
    assert isinstance(progress_bar, tqdm)
    assert progress_bar.total == 1000
    assert progress_bar.desc == "Uploading"  # Test desc directly
    progress_bar.close()


@pytest.mark.parametrize(
    "size,expected",
    [
        (500, "500.00 B"),
        (1024, "1.00 KB"),
        (1024 * 1024, "1.00 MB"),
        (1024 * 1024 * 1024, "1.00 GB"),
        (1024 * 1024 * 1024 * 1024, "1.00 TB"),
        (1024 * 1024 * 1024 * 1024 * 1024, "1.00 PB"),
    ],
)
def test_format_size(size, expected):
    """Test size formatting for various sizes."""
    assert format_size(size) == expected


def test_format_size_zero():
    """Test size formatting for zero bytes."""
    assert format_size(0) == "0.00 B"


def test_format_size_small():
    """Test size formatting for small values."""
    assert format_size(10) == "10.00 B"


def test_format_size_fractional():
    """Test size formatting for fractional values."""
    assert format_size(1536) == "1.50 KB"  # 1.5 KB


@pytest.mark.parametrize(
    "total,speed,completed,expected",
    [
        (1000, 100, 0, "10s"),  # 10 seconds
        (1000, 10, 0, "100s"),  # 100 seconds
        (3600, 1, 0, "1.0h"),  # 1 hour
        (7200, 1, 0, "2.0h"),  # 2 hours
        (1000, 100, 500, "5s"),  # 5 seconds with partial completion
        (1000, 0, 0, "unknown"),  # Zero speed
    ],
)
def test_estimate_time(total, speed, completed, expected):
    """Test time estimation for various scenarios."""
    assert estimate_time(total, speed, completed) == expected


def test_estimate_time_completed():
    """Test time estimation when transfer is complete."""
    assert estimate_time(1000, 100, 1000) == "0s"


def test_estimate_time_zero_remaining():
    """Test time estimation when no bytes remain."""
    assert estimate_time(1000, 100, 1000) == "0s"


def test_progress_bar_updates():
    """Test progress bar updates correctly."""
    with create_progress_bar(total=100, desc="Testing") as pbar:
        assert pbar.n == 0
        pbar.update(50)
        assert pbar.n == 50
        pbar.update(50)
        assert pbar.n == 100


def test_progress_bar_context_manager():
    """Test progress bar works as context manager."""
    with create_progress_bar(total=100) as pbar:
        assert hasattr(pbar, "close")
        # Update to completion
        pbar.update(100)
    assert pbar.n == pbar.total


def test_progress_bar_disable():
    """Test progress bar can be disabled."""
    progress_bar = create_progress_bar(total=100, disable=True)
    assert progress_bar.disable is True
    progress_bar.close()


def test_progress_bar_unit_conversion():
    """Test progress bar unit conversion."""
    with create_progress_bar(
        total=2048, unit="B", unit_scale=True, unit_divisor=1024
    ) as pbar:
        pbar.update(1024)
        assert (
            pbar.format_sizeof(pbar.n).replace(" ", "") == "1.02k"
        )  # Match actual format
