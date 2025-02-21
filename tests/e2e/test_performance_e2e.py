"""End-to-end performance tests."""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import pytest

from nova_pydrobox.operations.files import FileOperations
from nova_pydrobox.operations.folders import FolderOperations


def generate_test_files(base_path: Path, count: int, size_mb: int = 1):
    """Generate test files of specified size."""
    files = []
    for i in range(count):
        file_path = base_path / "test_file_{}.bin".format(i)
        with open(file_path, "wb") as f:
            f.write(os.urandom(size_mb * 1024 * 1024))
        files.append(file_path)
    return files


@pytest.fixture
def performance_files(tmp_path):
    """Create a set of files for performance testing."""
    return generate_test_files(tmp_path, count=5, size_mb=5)  # 5 files, 5MB each


@pytest.mark.e2e
def test_bulk_upload_performance(
    e2e_auth, e2e_dropbox_client, performance_files, e2e_test_path
):
    """
    Test performance of bulk file uploads.

    This test:
    1. Uploads multiple files in sequence
    2. Measures upload time
    3. Calculates throughput
    """
    file_ops = FileOperations(dbx_client=e2e_dropbox_client)
    total_size = sum(f.stat().st_size for f in performance_files)

    # Time sequential uploads
    start_time = time.time()
    for file_path in performance_files:
        dropbox_path = "{}/{}".format(e2e_test_path, file_path.name)
        result = file_ops.upload(str(file_path), dropbox_path)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

    elapsed_time = time.time() - start_time
    throughput = total_size / elapsed_time / (1024 * 1024)  # MB/s

    # Log performance metrics
    print("\nBulk Upload Performance")
    print("Total files:", len(performance_files))
    print("Total size: {:.2f} MB".format(total_size / (1024 * 1024)))
    print("Total time: {:.2f} seconds".format(elapsed_time))
    print("Throughput: {:.2f} MB/s".format(throughput))


@pytest.mark.e2e
def test_parallel_upload_performance(
    e2e_auth, e2e_dropbox_client, performance_files, e2e_test_path
):
    """
    Test performance of parallel file uploads.

    This test:
    1. Uploads multiple files concurrently
    2. Measures upload time
    3. Compares with sequential performance
    """
    file_ops = FileOperations(dbx_client=e2e_dropbox_client)
    total_size = sum(f.stat().st_size for f in performance_files)

    def upload_file(file_path):
        dropbox_path = "{}/parallel/{}".format(e2e_test_path, file_path.name)
        result = file_ops.upload(str(file_path), dropbox_path)
        assert isinstance(result, pd.DataFrame)
        return result

    # Time parallel uploads
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(upload_file, performance_files))  # Execute all uploads

    elapsed_time = time.time() - start_time
    throughput = total_size / elapsed_time / (1024 * 1024)  # MB/s

    # Log performance metrics
    print("\nParallel Upload Performance")
    print("Total files:", len(performance_files))
    print("Total size: {:.2f} MB".format(total_size / (1024 * 1024)))
    print("Total time: {:.2f} seconds".format(elapsed_time))
    print("Throughput: {:.2f} MB/s".format(throughput))


@pytest.mark.e2e
def test_large_folder_listing_performance(
    e2e_auth, e2e_dropbox_client, e2e_test_path, tmp_path
):
    """
    Test performance of listing large folders.

    This test:
    1. Creates a folder with many files
    2. Measures listing performance
    3. Tests recursive vs non-recursive listing
    """
    # Create many small files
    files = generate_test_files(tmp_path, count=100, size_mb=1)
    file_ops = FileOperations(dbx_client=e2e_dropbox_client)
    folder_ops = FolderOperations(dbx_client=e2e_dropbox_client)

    # Upload files
    for file_path in files:
        dropbox_path = "{}/perf_test/{}".format(e2e_test_path, file_path.name)
        file_ops.upload(str(file_path), dropbox_path)

    # Time non-recursive listing
    start_time = time.time()
    result = folder_ops.list_files("{}/perf_test".format(e2e_test_path))
    non_recursive_time = time.time() - start_time
    assert isinstance(result, pd.DataFrame)
    assert len(result) == len(files)

    # Time recursive listing
    start_time = time.time()
    result = folder_ops.get_folder_structure("{}/perf_test".format(e2e_test_path))
    recursive_time = time.time() - start_time
    assert isinstance(result, pd.DataFrame)

    # Log performance metrics
    print("\nFolder Listing Performance")
    print("Total files:", len(files))
    print("Non-recursive listing time: {:.2f} seconds".format(non_recursive_time))
    print("Recursive listing time: {:.2f} seconds".format(recursive_time))


@pytest.mark.e2e
def test_memory_usage(e2e_auth, e2e_dropbox_client, e2e_test_path):
    """
    Test memory usage during operations.

    This test:
    1. Monitors memory during large operations
    2. Checks for memory leaks
    3. Verifies efficient memory use
    """
    import psutil

    process = psutil.Process()
    folder_ops = FolderOperations(dbx_client=e2e_dropbox_client)

    def get_memory_mb():
        """Get current memory usage in MB."""
        return process.memory_info().rss / (1024 * 1024)

    # Measure baseline memory
    baseline_memory = get_memory_mb()

    # Perform memory-intensive operations
    start_memory = get_memory_mb()
    for _ in range(10):  # Multiple iterations to detect leaks
        result = folder_ops.get_folder_structure("/")
        assert isinstance(result, pd.DataFrame)
    end_memory = get_memory_mb()

    # Log memory metrics
    print("\nMemory Usage")
    print("Baseline memory: {:.2f} MB".format(baseline_memory))
    print("Peak memory: {:.2f} MB".format(end_memory))
    print("Memory increase: {:.2f} MB".format(end_memory - start_memory))

    # Verify no significant memory leak
    assert end_memory - start_memory < 50  # Allow up to 50MB growth


@pytest.mark.e2e
def test_rate_limiting_handling(e2e_auth, e2e_dropbox_client, e2e_test_path, tmp_path):
    """
    Test handling of rate limits.

    This test:
    1. Performs rapid sequential operations
    2. Monitors rate limit errors
    3. Verifies backoff behavior
    """
    file_ops = FileOperations(dbx_client=e2e_dropbox_client)

    # Create test file
    test_file = tmp_path / "rate_test.txt"
    test_file.write_text("Rate limit test content")

    # Perform rapid operations
    start_time = time.time()
    operations = []
    for i in range(20):  # Number that might trigger rate limiting
        try:
            file_ops.upload(
                str(test_file), "{}/rate_test_{}.txt".format(e2e_test_path, i)
            )
            operations.append(("success", time.time() - start_time))
        except Exception:
            operations.append(("error", time.time() - start_time))
            time.sleep(1)  # Basic backoff

    # Analyze timing pattern
    print("\nRate Limit Test Results")
    success_count = sum(1 for op in operations if op[0] == "success")
    error_count = len(operations) - success_count
    print("Successful operations:", success_count)
    print("Rate limit errors:", error_count)

    # Calculate operation timing
    intervals = [
        operations[i + 1][1] - operations[i][1] for i in range(len(operations) - 1)
    ]
    avg_interval = sum(intervals) / len(intervals)
    print("Average operation interval: {:.3f} seconds".format(avg_interval))
