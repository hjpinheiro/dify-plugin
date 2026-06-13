# Design: Upgrade Daytona Dify Agent Tools v0.0.9

## Overview

The plugin remains a Dify **tool provider**, not an Agent Strategy plugin. Dify's
official `langgenius/agent` plugin already provides Function Calling and ReAct
strategies that invoke this provider's tools.

This release prioritizes reliability over breadth. The single highest-impact fix
is transparent reactivation of stopped sandboxes; everything else builds on a
robust, stateful-enough core that an LLM can drive with fewer mistakes.

All work targets the Daytona Python SDK API shape observed in `0.187.0` and the
Dify Plugin SDK helpers available in the deployed plugin daemon.

## Verified SDK surface (Daytona 0.187.0)

Confirmed by local inspection of the installed SDK:

- `Sandbox.start()`, `Sandbox.stop()`, `Sandbox.archive()`
- `Sandbox.wait_for_sandbox_start()`, `Sandbox.wait_for_sandbox_stop()`
- `Daytona.start(sandbox)`, `Daytona.stop(sandbox)`
- `SandboxState` enum values include: `STARTED`, `STOPPED`, `STOPPING`,
  `STARTING`, `ARCHIVED`, `ARCHIVING`, `CREATING`, `ERROR`, `DESTROYED`,
  `RESTORING`, `UNKNOWN`.
- `Process.exec(command, cwd, env, timeout) -> ExecuteResponse`
- `Process.code_run(code, params, timeout) -> ExecuteResponse`
- `Process.create_session(session_id)`,
  `Process.execute_session_command(session_id, SessionExecuteRequest, timeout)`,
  `Process.get_session_command_logs(session_id, cmd_id, ...)`,
  `Process.get_session(session_id)`, `Process.delete_session(session_id)`,
  `Process.list_sessions()`.
- `SessionExecuteRequest` fields include `command`, `var_async` (and `run_async`),
  `suppress_input_echo`.
- `ExecuteResponse` fields: `exit_code`, `result`, `artifacts`,
  `additional_properties`. `artifacts` exposes `stdout` and `charts` (matplotlib
  chart metadata; each chart may include `png` base64, `type`, `title`, axis
  labels and elements).
- `Sandbox.get_preview_link(port) -> preview(url, token)`.
- `Sandbox.create_signed_preview_url(...)` and
  `Sandbox.expire_signed_preview_url(...)` exist for time-limited previews.

> Note on state values: read state defensively as
> `getattr(sandbox.state, "value", sandbox.state)` and compare case-insensitively,
> because the SDK returns an enum whose `.value` is a lowercase string.

## Verified Dify Plugin SDK surface

- `self.session.storage.set(key: str, value: bytes)`,
  `get(key) -> bytes` (raises if missing), `exist(key) -> bool`,
  `delete(key)`. Values are bytes; encode/decode UTF-8 or JSON.
- `ToolLike` message helpers: `create_text_message`, `create_json_message`,
  `create_blob_message`, `create_image_message`, `create_link_message`,
  `create_variable_message`, `create_stream_variable_message`,
  `create_log_message`, `finish_log_message`.

## 1. Transparent sandbox reactivation (critical)

Extend the shared `get_sandbox()` helper in `_client.py` so a reused sandbox is
usable regardless of idle state.

```python
def get_sandbox(client, sandbox_id, *, auto_start=True, wait=True):
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

    if auto_start and state in ("stopped", "archived"):
        with daytona_operation("starting sandbox"):
            sandbox.start()
            if wait:
                sandbox.wait_for_sandbox_start()
        sandbox = client.get(sandbox_id)  # refresh state/handles
    elif state in ("error", "destroyed", "destroying"):
        raise ValueError(
            f"Sandbox '{sandbox_id}' is in state '{state}' and cannot be used."
        )
    return sandbox
```

Design notes:

- Default `auto_start=True`. Execution/file tools rely on it. Pure-metadata
  paths may pass `auto_start=False`.
- Starting an `ARCHIVED` sandbox restores it; this can be slower, so the
  `wait_for_sandbox_start()` call must respect a reasonable bound and surface a
  clear error on timeout.
- Reads must be defensive about the state enum representation.

## 2. Active sandbox memory via session storage

Persist the most recently used sandbox per conversation so the agent does not
have to carry `sandbox_id` through every call.

- Storage key: a constant such as `active_sandbox_id`.
- Helpers in `_client.py`:
  - `remember_sandbox(tool, sandbox_id)` -> `tool.session.storage.set(...)`
  - `recall_sandbox(tool)` -> returns stored id or `None`
  - `forget_sandbox(tool)` -> delete on destroy
- Resolution order for any tool needing a sandbox:
  1. explicit `sandbox_id` parameter, else
  2. `recall_sandbox(tool)`, else
  3. raise a clear error instructing the agent to create or pass a sandbox.
- Write the active id on `create_sandbox`, and on `run_code` / `run_command`
  when a persistent (non-ephemeral) sandbox is used.
- Clear it on `destroy_sandbox` when it matches the stored id.

Safety:

- Storage is best-effort. Wrap reads/writes so storage failures never break the
  primary operation; treat a storage miss as "no active sandbox".
- Never store credentials in session storage. Only the sandbox id.
- Do not auto-resolve for `destroy_sandbox` unless the caller passes no id AND a
  stored id exists; deletion should remain explicit and logged.

## 3. Background execution and `start_service`

Use Daytona sessions for long-running processes.

- Add a `start_service` tool that:
  1. resolves the sandbox (reactivating if needed),
  2. creates (or reuses) a session id,
  3. runs the command with `SessionExecuteRequest(command=..., var_async=True)`,
  4. returns immediately with `session_id`, `cmd_id`, and guidance to call
     `get_preview_url` for the service port.
- Optionally capture the first slice of logs via
  `get_session_command_logs` for a short bounded window so the agent gets early
  feedback (startup errors), then stop reading.
- Add a companion behavior or small tool to fetch later logs by
  `session_id`/`cmd_id` (bounded), so the agent can confirm the service is up.
- `run_command` keeps synchronous semantics for short commands. Do not change its
  default behavior; background execution is a distinct tool to keep selection
  unambiguous for the LLM.

Pairing with preview:

- Document the canonical flow in the `start_service` and `get_preview_url` LLM
  descriptions: start service on a port in 3000–9999, then get its preview URL.

## 4. Sandbox lifecycle tools

Add three additive tools that map directly to the SDK:

- `start_sandbox(sandbox_id)` -> `sandbox.start()` + optional wait; return new
  state.
- `stop_sandbox(sandbox_id)` -> `sandbox.stop()`; return new state. Use for cost
  control without losing filesystem state.
- `archive_sandbox(sandbox_id)` -> `sandbox.archive()`; return new state.

Each returns JSON (`sandbox_id`, `state`) and a concise text summary. These are
additive and must not change existing tool behavior.

## 5. Chart artifact metadata in `run_code`

Keep yielding `chart.png` as a blob, but also include chart metadata in the JSON
payload so the agent can describe the visualization:

```python
charts_meta = []
for chart in (charts or []):
    charts_meta.append({
        "type": getattr(chart, "type", None),
        "title": getattr(chart, "title", None),
    })
# json: { ..., "charts_count": n, "charts": charts_meta }
```

Read every attribute defensively with `getattr`, since chart subtypes differ and
some fields may be absent.

## 6. Workflow variable outputs

For Dify Workflow chaining, emit named variables in addition to existing
text/json messages:

- `create_sandbox`: `create_variable_message("sandbox_id", sandbox.id)`
- `run_code` / `run_command`: `create_variable_message("sandbox_id", sandbox.id)`
  for persistent sandboxes, and `create_variable_message("exit_code", ...)`.
- `get_preview_url`: `create_variable_message("preview_url", preview.url)`.

These are additive; agent (ReAct/FC) behavior is unchanged because it reads
text/json observations.

## 7. Structured logs for long operations

Use `create_log_message` / `finish_log_message` to give UI feedback during slow
operations:

- `create_sandbox` (up to 180s create timeout, plus archive restore).
- `git_clone`.
- `start_service` startup.

Logs are supplementary; the final text/json result contract is unchanged.

## 8. Signed preview URLs (optional, lower priority)

Where the use case calls for sharing a private preview, prefer
`create_signed_preview_url(...)` (time-limited) over returning the raw token.
Keep `include_token=false` as the default for `get_preview_url`. This requirement
is optional for this release and may be deferred if the SDK signature needs
further validation.

## 9. Packaging safety gate

Add a validation step to `package.py` (or a pre-package check) that:

- parses every `*.yaml` under the repo (`manifest.yaml`, `provider/*.yaml`,
  `tools/*.yaml`) with a YAML loader and fails on any parse error,
- asserts `manifest.yaml` has top-level `version` and `meta.version` equal,
- asserts every tool registered in `provider/daytona.yaml` has matching YAML and
  Python source files,
- asserts the resulting zip contains files only (no directory entries).

This directly prevents the v0.0.8 manifest corruption from shipping again.

## Tool surface after this change

Existing (14): `create_sandbox`, `run_code`, `run_command`, `upload_file`,
`download_file`, `read_file`, `write_file`, `get_preview_url`, `destroy_sandbox`,
`list_files`, `search_files`, `find_in_files`, `git_clone`, `list_sandboxes`.

Added (up to 4): `start_service`, `start_sandbox`, `stop_sandbox`,
`archive_sandbox`.

> Consolidation/renaming to reduce the tool count for ReAct reliability is
> explicitly deferred to a future change because renaming breaks installed agent
> configurations. If pursued later, keep old tool names as registered aliases for
> one release.

## Risks

- **Auto-start latency.** Reactivating a stopped/archived sandbox adds latency to
  the first call of a turn. Mitigate with clear logs and bounded waits.
- **Session lifecycle leaks.** Background sessions can linger. Use deterministic
  session ids and document cleanup; rely on `auto_stop_interval` as a backstop.
- **Session storage scope.** Confirm `session.storage` scoping (per conversation
  vs per app) in the deployed daemon before relying on it for the active sandbox;
  fall back gracefully if behavior differs.
- **State enum drift.** Compare state values defensively (lowercased `.value`).
- **Backward compatibility.** All additions must be opt-in/additive; existing tool
  names, parameters, and default behaviors must not change.
