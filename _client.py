import hashlib
import json
import logging
import os
import re
import shlex
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
    """Find a sandbox labeled with the given conversation_id.

    Uses CLIENT-SIDE label filtering (lists all sandboxes, then checks labels locally)
    instead of relying on the API's label query parameter, which may not work reliably.
    """
    if not conversation_id:
        return None
    for sb in _list_usable_sandboxes(client):
        labels = getattr(sb, "labels", None) or {}
        if labels.get(_CONVERSATION_LABEL_KEY) == conversation_id:
            return sb.id
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


def _list_usable_sandboxes(client: Daytona) -> list:
    """List all sandboxes in usable states, sorted by created_at descending.

    Internal helper shared by all discovery functions. Filters out error/destroyed
    states and sorts newest-first so the most recent sandbox is preferred.
    """
    try:
        query = ListSandboxesQuery(
            states=[SandboxState.STARTED, SandboxState.STOPPED, SandboxState.ARCHIVED,
                    SandboxState.STARTING],
        )
        sandboxes = list(client.list(query))
        usable = []
        for sb in sandboxes:
            state = getattr(sb.state, "value", sb.state)
            state = (state or "").lower()
            if state in ("error", "destroyed", "destroying"):
                continue
            usable.append(sb)
        usable.sort(key=lambda sb: getattr(sb, "created_at", "") or "", reverse=True)
        return usable
    except Exception:
        logger.warning("Failed to list sandboxes", exc_info=True)
        return []


def label_sandbox(client: Daytona, sandbox_id: str, conversation_id: str) -> bool:
    """Apply the conversation_id label to a sandbox (Dynamic Promotion).

    Used when a sandbox is claimed via find_any_sandbox fallback — labeling it
    locks it to this conversation so future lookups find it via the primary path.
    Returns True on success, False on failure.
    """
    if not conversation_id:
        return False
    try:
        sandbox = client.get(sandbox_id)
        existing_labels = getattr(sandbox, "labels", None) or {}
        existing_labels[_CONVERSATION_LABEL_KEY] = conversation_id
        sandbox.set_labels(existing_labels)
        return True
    except Exception:
        logger.warning("Failed to label sandbox %s with conversation_id %s", sandbox_id, conversation_id, exc_info=True)
        return False


def find_any_sandbox(client: Daytona) -> str | None:
    """Find the most recent UNLABELED usable sandbox.

    Excludes sandboxes that have a dify_conversation_id label (they belong to
    other conversations). Unlabeled sandboxes are fair game — they will be
    claimed via Dynamic Promotion (label_sandbox) by the caller.
    """
    for sb in _list_usable_sandboxes(client):
        labels = getattr(sb, "labels", None) or {}
        if _CONVERSATION_LABEL_KEY in labels:
            continue
        return sb.id
    return None


def resolve_sandbox_id(tool: Any, tool_parameters: dict[str, Any]) -> str:
    """Resolve sandbox_id using cascading strategies.

    Priority order:
      1. Explicit sandbox_id parameter (highest)
      2. recall_sandbox() — per-invocation cache (same-call only)
      3. find_sandbox_by_conversation() — client-side label match (cross-invocation)
      4. find_any_sandbox() — most recent unlabeled sandbox (fallback for null conversation_id)
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

    # Last resort fallback: most recent unlabeled sandbox (crucial when conversation_id is null)
    any_found = find_any_sandbox(daytona)
    if any_found:
        remember_sandbox(tool, any_found)
        return any_found

    raise ValueError(
        "No sandbox_id provided and no active sandbox found for this conversation. "
        "Create a sandbox first using create_sandbox, or provide sandbox_id explicitly."
    )


def try_resolve_sandbox_id(tool: Any, tool_parameters: dict[str, Any]) -> str | None:
    """Like resolve_sandbox_id but returns None instead of raising.

    Priority order:
      1. Explicit sandbox_id parameter (highest)
      2. recall_sandbox() — per-invocation cache (same-call only)
      3. find_sandbox_by_conversation() — client-side label match (cross-invocation)
      4. find_any_sandbox() — most recent unlabeled sandbox (fallback for null conversation_id)
      5. Return None if all strategies fail
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

    # Last resort fallback: most recent unlabeled sandbox (crucial when conversation_id is null)
    any_found = find_any_sandbox(daytona)
    if any_found:
        remember_sandbox(tool, any_found)
        return any_found

    return None


# ---------------------------------------------------------------
# Shared helper functions (added for run_command, start_service,
# run_code refactors)
# ---------------------------------------------------------------


def shared_command_session_id(conversation_id: str | None, sandbox_id: str) -> str:
    """Derive a deterministic session ID from conversation_id + sandbox_id.

    Pure function with no side effects. Format: cmd-<sha1 hex[:16]>.
    """
    cid = conversation_id if conversation_id else "none"
    digest = hashlib.sha1(f"{cid}:{sandbox_id}".encode()).hexdigest()[:16]
    return f"cmd-{digest}"


def get_or_create_command_session(sandbox: Any, session_id: str) -> None:
    """Get an existing Daytona session or create it if missing.

    Idempotent: calling when the session already exists does not error.
    """
    try:
        sandbox.process.get_session(session_id)
        return
    except Exception:
        pass

    with daytona_operation("creating command session"):
        sandbox.process.create_session(session_id)


def compose_shell_command(
    command: str,
    cwd: str | None = None,
    env_vars: dict[str, str] | None = None,
) -> str:
    """Build a shell command string that applies cwd and env_vars before the command.

    Pure function. Uses shlex.quote for safe shell quoting of all values.
    Order: cd <cwd> && export KEY=val && ... && <command>.
    """
    parts = []

    if cwd is not None:
        parts.append(f"cd {shlex.quote(cwd)}")

    if env_vars:
        for key, value in env_vars.items():
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key):
                raise ValueError(f"Invalid environment variable name: {key!r}")
            parts.append(f"export {key}={shlex.quote(value)}")

    parts.append(command)

    return " && ".join(parts)


def inject_text_files(sandbox: Any, text_files_json: str) -> list[str]:
    """Inject text files into the sandbox workspace at /home/daytona/workspace.

    Parses text_files_json as a JSON object mapping workspace-relative paths
    to text content. Performs path traversal checks, creates parent
    directories, and uploads content as UTF-8.

    Returns the list of full paths that were written.
    """
    try:
        text_files = json.loads(text_files_json)
    except (json.JSONDecodeError, TypeError) as e:
        raise ValueError(f"text_files_json is not valid JSON: {e}") from e

    if not isinstance(text_files, dict):
        raise ValueError("text_files_json must be a JSON object mapping paths to content")

    workspace_root = "/home/daytona/workspace"
    written_paths = []

    for rel_path, content in text_files.items():
        if not isinstance(rel_path, str) or not rel_path:
            raise ValueError(f"Invalid relative path: {rel_path!r}")

        if rel_path.startswith("/"):
            raise ValueError(f"Absolute paths are not allowed: {rel_path!r}")

        full_path = os.path.normpath(os.path.join(workspace_root, rel_path))

        if not full_path.startswith(workspace_root + "/") and full_path != workspace_root:
            raise ValueError(f"Path traversal rejected: {rel_path!r}")

        dir_path = os.path.dirname(full_path)
        if dir_path:
            with daytona_operation(f"creating directory {dir_path}"):
                sandbox.process.exec(f"mkdir -p {shlex.quote(dir_path)}")

        with daytona_operation(f"uploading file {rel_path}"):
            sandbox.fs.upload_file(str(content).encode("utf-8"), full_path)

        written_paths.append(full_path)

    return written_paths
