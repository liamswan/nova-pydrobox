from pathlib import Path
from typing import Dict, List, Optional, TypedDict, Union

from pandas import DataFrame


class TokenData(TypedDict):
    """Type definition for authentication tokens"""

    app_key: str
    app_secret: str
    access_token: str
    refresh_token: str


class FileMetadata(TypedDict):
    """Type definition for file metadata"""

    name: str
    path: str
    type: str
    size: int
    modified: Optional[str]
    hash: Optional[str]


class OperationResult(TypedDict):
    """Type definition for operation results"""

    success: bool
    data: Optional[Union[FileMetadata, List[FileMetadata]]]
    error: Optional[str]


# Type aliases for common types
PathLike = Union[str, Path]
DataFrameResult = DataFrame
MetadataDict = Dict[str, Union[str, int, None]]
