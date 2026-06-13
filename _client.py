import hashlib
import logging
from typing import Any

from daytona import Daytona, DaytonaConfig, DaytonaError, DaytonaNotFoundError, Sandbox

logger = logging.getLogger(__name__)

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
    except DaytonaError as e:
        raise ValueError(f"Failed to retrieve sandbox '{sandbox_id}': {e}") from e
    if sandbox is None:
        raise ValueError(f"Sandbox '{sandbox_id}' not found")
    return sandbox
