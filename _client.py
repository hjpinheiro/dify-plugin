import hashlib
import logging
from contextlib import contextmanager
from typing import Any

from daytona import Daytona, DaytonaConfig, DaytonaError, DaytonaNotFoundError, Sandbox

logger = logging.getLogger(__name__)

VALID_LANGUAGES = ("python", "typescript", "javascript")
EXECUTION_TIMEOUT = 120
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

_client_cache: dict[str, Daytona] = {}


def _cache_key(credentials: dict[str, Any]) -> str:
    raw = f"{credentials.get('api_key', '')}:{credentials.get('api_url', '')}"
    return hashlib.sha256(raw.encode()).hexdigest()


def build_client(credentials: dict[str, Any]) -> Daytona:
    key = _cache_key(credentials)
    if key not in _client_cache:
        config = DaytonaConfig(api_key=credentials["api_key"])
        if api_url := credentials.get("api_url"):
            config.api_url = api_url
        _client_cache[key] = Daytona(config)
    return _client_cache[key]


def get_sandbox(client: Daytona, sandbox_id: str) -> Sandbox:
    if not sandbox_id:
        raise ValueError("sandbox_id is required")
    try:
        sandbox = client.get(sandbox_id)
    except DaytonaNotFoundError as e:
        raise ValueError(f"Sandbox '{sandbox_id}' not found") from e
    if sandbox is None:
        raise ValueError(f"Sandbox '{sandbox_id}' not found")
    return sandbox


def validate_language(language: str) -> str:
    if language not in VALID_LANGUAGES:
        raise ValueError(
            f"Invalid language: '{language}'. Must be one of: {', '.join(VALID_LANGUAGES)}."
        )
    return language


@contextmanager
def daytona_operation(operation: str):
    try:
        yield
    except DaytonaNotFoundError as e:
        raise ValueError(f"Resource not found during {operation}: {e}") from e
    except DaytonaError as e:
        raise ValueError(f"Daytona error during {operation}: {e}") from e
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        logger.exception("Unexpected error during %s", operation)
        raise ValueError(f"Unexpected error during {operation}: {e}") from e
