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


def get_sandbox(client: Daytona, sandbox_id: str, *, auto_start: bool = True, wait: bool = True) -> Sandbox:
    if not sandbox_id:
        raise ValueError("sandbox_id is required")
    try:
        sandbox = client.get(sandbox_id)
    except DaytonaNotFoundError as e:
        raise ValueError(f"Sandbox '{sandbox_id}' not found") from e
    if sandbox is None:
        raise ValueError(f"Sandbox '{sandbox_id}' not found")

    state = getattr(sandbox.state, "value", sandbox.state)
    state = (state or "").lower()

    if state in ("error", "destroyed", "destroying"):
        raise ValueError(f"Sandbox '{sandbox_id}' is in state '{state}' and cannot be used.")

    if state in ("stopped", "archived") and auto_start:
        with daytona_operation("starting sandbox"):
            sandbox.start()
            if wait:
                try:
                    sandbox.wait_for_sandbox_start()
                except Exception as e:
                    if isinstance(e, ValueError):
                        raise
                    raise ValueError(f"Failed to start sandbox '{sandbox_id}' (wait timeout or error): {e}") from e
        sandbox = client.get(sandbox_id)

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


_STORAGE_KEY = "active_sandbox_id"


def remember_sandbox(tool: Any, sandbox_id: str) -> None:
    try:
        tool.session.storage.set(_STORAGE_KEY, sandbox_id.encode("utf-8"))
    except Exception:
        pass


def recall_sandbox(tool: Any) -> str | None:
    try:
        if tool.session.storage.exist(_STORAGE_KEY):
            return tool.session.storage.get(_STORAGE_KEY).decode("utf-8")
    except Exception:
        pass
    return None


def forget_sandbox(tool: Any) -> None:
    try:
        tool.session.storage.delete(_STORAGE_KEY)
    except Exception:
        pass


def resolve_sandbox_id(tool: Any, tool_parameters: dict[str, Any]) -> str:
    sandbox_id = tool_parameters.get("sandbox_id") or ""
    if sandbox_id:
        return sandbox_id
    stored = recall_sandbox(tool)
    if stored:
        return stored
    raise ValueError(
        "No sandbox_id provided and no active sandbox found in this conversation. "
        "Create a sandbox first using create_sandbox, or provide sandbox_id explicitly."
    )
