import hashlib
import logging
from contextlib import contextmanager
from typing import Any

from daytona import (
    Daytona,
    DaytonaConfig,
    DaytonaError,
    DaytonaNotFoundError,
    ListSandboxesQuery,
    Sandbox,
    SandboxState,
)

logger = logging.getLogger(__name__)

VALID_LANGUAGES = ("python", "typescript", "javascript")
EXECUTION_TIMEOUT = 120
MAX_EXECUTION_TIMEOUT = 600
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

_CONVERSATION_LABEL_KEY = "dify_conversation_id"

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


def resolve_timeout(raw: Any) -> int | None:
    if raw is None or raw == "":
        return None
    timeout = int(raw)
    if timeout < 1:
        timeout = 1
    if timeout > MAX_EXECUTION_TIMEOUT:
        timeout = MAX_EXECUTION_TIMEOUT
    return timeout


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


def get_conversation_id(tool: Any) -> str | None:
    try:
        conv_id = getattr(tool.session, "conversation_id", None)
        if conv_id and conv_id != "":
            return str(conv_id)
    except Exception:
        pass
    return None


def find_sandbox_by_conversation(client: Daytona, conversation_id: str) -> str | None:
    if not conversation_id:
        return None
    try:
        query = ListSandboxesQuery(
            labels={_CONVERSATION_LABEL_KEY: conversation_id},
            states=[SandboxState.STARTED, SandboxState.STOPPED, SandboxState.ARCHIVED,
                    SandboxState.STARTING],
        )
        sandboxes = list(client.list(query))
        if not sandboxes:
            return None
        # Sort by created_at descending — prioritize the most recently created sandbox
        sandboxes.sort(key=lambda sb: getattr(sb, "created_at", "") or "", reverse=True)
        for sb in sandboxes:
            state = getattr(sb.state, "value", sb.state)
            state = (state or "").lower()
            if state in ("error", "destroyed", "destroying"):
                continue
            return sb.id
    except Exception:
        logger.warning("Failed to list sandboxes by conversation_id %s", conversation_id, exc_info=True)
    return None


def remember_sandbox(tool: Any, sandbox_id: str) -> None:
    """Store sandbox_id in session.storage.

    NOTE: session.storage is keyed by the SDK invocation session_id, which is unique
    per tool-invocation request. This storage does NOT persist across separate tool calls
    in a conversation. Use find_sandbox_by_conversation() for cross-invocation reuse.
    This function is only useful within the same invocation (e.g., create_sandbox
    remembers the id it just created for downstream logic in the same call).
    """
    try:
        tool.session.storage.set(_STORAGE_KEY, sandbox_id.encode("utf-8"))
    except Exception:
        pass


def recall_sandbox(tool: Any) -> str | None:
    """Retrieve sandbox_id from session.storage.

    NOTE: Per-invocation only — see remember_sandbox. Will return None if called
    from a different tool invocation than where remember_sandbox was called.
    """
    try:
        if tool.session.storage.exist(_STORAGE_KEY):
            return tool.session.storage.get(_STORAGE_KEY).decode("utf-8")
    except Exception:
        pass
    return None


def forget_sandbox(tool: Any) -> None:
    """Delete sandbox_id from session.storage.

    NOTE: Per-invocation only — see remember_sandbox. Best-effort; failures are silent.
    """
    try:
        tool.session.storage.delete(_STORAGE_KEY)
    except Exception:
        pass


def find_any_sandbox(client: Daytona) -> str | None:
    """Find the most recent usable sandbox (fallback when conversation_id is unavailable).

    This is a safety net for tool-testing mode or when conversation_id is None.
    Only returns sandboxes in usable states; excludes error/destroyed/destroying.
    """
    try:
        query = ListSandboxesQuery(
            states=[SandboxState.STARTED, SandboxState.STOPPED, SandboxState.ARCHIVED,
                    SandboxState.STARTING],
        )
        sandboxes = list(client.list(query))
        if not sandboxes:
            return None
        usable = []
        for sb in sandboxes:
            state = getattr(sb.state, "value", sb.state)
            state = (state or "").lower()
            if state in ("error", "destroyed", "destroying"):
                continue
            # SECURITY: Exclude sandboxes that belong to a specific conversation
            sb_labels = getattr(sb, "labels", None) or {}
            if _CONVERSATION_LABEL_KEY in sb_labels:
                continue
            usable.append(sb)
        if not usable:
            return None
        usable.sort(key=lambda sb: getattr(sb, "created_at", "") or "", reverse=True)
        return usable[0].id
    except Exception:
        logger.warning("Failed to list sandboxes for fallback", exc_info=True)
        return None


def resolve_sandbox_id(tool: Any, tool_parameters: dict[str, Any]) -> str:
    """Resolve sandbox_id using cascading strategies.

    Priority order:
      1. Explicit sandbox_id parameter (highest)
      2. recall_sandbox() — per-invocation cache (same-call only)
      3. find_sandbox_by_conversation() — label-based, cross-invocation (primary)
      4. find_any_sandbox() — most recent sandbox (fallback, only when no conversation_id)
      5. Raise ValueError if all strategies fail
    """
    sandbox_id = tool_parameters.get("sandbox_id") or ""
    if sandbox_id:
        return sandbox_id

    stored = recall_sandbox(tool)
    if stored:
        return stored

    conv_id = get_conversation_id(tool)
    daytona = build_client(tool.runtime.credentials)

    if conv_id:
        found = find_sandbox_by_conversation(daytona, conv_id)
        if found:
            remember_sandbox(tool, found)
            return found

    if not conv_id:
        found = find_any_sandbox(daytona)
        if found:
            remember_sandbox(tool, found)
            return found

    raise ValueError(
        "No sandbox_id provided and no active sandbox found in this conversation. "
        "Create a sandbox first using create_sandbox, or provide sandbox_id explicitly."
    )


def try_resolve_sandbox_id(tool: Any, tool_parameters: dict[str, Any]) -> str | None:
    """Like resolve_sandbox_id but returns None instead of raising."""
    sandbox_id = tool_parameters.get("sandbox_id") or ""
    if sandbox_id:
        return sandbox_id

    stored = recall_sandbox(tool)
    if stored:
        return stored

    conv_id = get_conversation_id(tool)
    daytona = build_client(tool.runtime.credentials)

    if conv_id:
        found = find_sandbox_by_conversation(daytona, conv_id)
        if found:
            remember_sandbox(tool, found)
            return found

    if not conv_id:
        found = find_any_sandbox(daytona)
        if found:
            remember_sandbox(tool, found)
            return found

    return None
