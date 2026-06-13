# Design: Upgrade Daytona Dify Agent Tools v0.0.12

## Overview

The plugin remains a Dify **tool provider**. This release is a refinement pass
driven by an API audit that confirmed all v0.0.10 SDK calls are correct against
Daytona Python SDK `0.187.0`. The work is therefore additive and conservative:
consolidate redundant lifecycle tools, make execution limits configurable, fix
the proxied-preview contract for private sandboxes, and bound `read_file` memory
use.

All changes preserve existing tool names, parameters, and default behaviors. New
parameters are optional and default to current behavior.

## Verified SDK surface (Daytona 0.187.0)

Re-confirmed by local inspection of the installed SDK:

- `Process.code_run(code: str, params: CodeRunParams | None = None, timeout: int |
  None = None) -> ExecuteResponse`
- `Process.exec(command: str, cwd: str | None = None, env: dict | None = None,
  timeout: int | None = None) -> ExecuteResponse`
- `Git.clone(url, path, branch=None, commit_id=None, username=None,
  password=None, insecure_skip_tls=None) -> None` (no explicit timeout argument)
- `Sandbox.start(timeout=60)`, `Sandbox.stop(timeout=60, force=False)`,
  `Sandbox.archive() -> None`, `Sandbox.wait_for_sandbox_start(timeout=60)`
- `Sandbox.get_preview_link(port) -> PortPreviewUrl` with `url` and `token`
- `FileSystem.get_file_info(path) -> FileInfo` (`size`, ...);
  `FileSystem.download_file(*args) -> bytes | None` (single arg returns bytes)

> `Git.clone` has no timeout parameter in `0.187.0`. The configurable git clone
> timeout must therefore be implemented at the plugin level (see section 2).

## 1. Consolidated lifecycle tool `manage_sandbox`

Add `tools/manage_sandbox.py` + `manage_sandbox.yaml`:

- Parameters:
  - `action` (required, select): one of `start`, `stop`, `archive`.
  - `sandbox_id` (optional): resolved via `resolve_sandbox_id` (explicit ->
    active -> clear error), matching existing lifecycle tools.
- Behavior maps directly to the SDK using `daytona.get(sandbox_id)` and then the
  matching method, with NO implicit auto-start (mirrors the current lifecycle
  tools, which deliberately avoid `get_sandbox(auto_start=True)` so that
  `stop`/`archive` do not start the sandbox first):

```python
sandbox = daytona.get(sandbox_id)
if action == "start":
    sandbox.start(); sandbox.wait_for_sandbox_start()
elif action == "stop":
    sandbox.stop()
elif action == "archive":
    sandbox.archive()
sandbox = daytona.get(sandbox_id)  # refresh state
```

- Returns JSON (`sandbox_id`, `action`, `state`) plus a concise text summary,
  identical in shape to the existing lifecycle tools.

### Deprecation strategy (backward compatible)

- `start_sandbox`, `stop_sandbox`, `archive_sandbox` remain **registered and
  functional** in this release so installed agents do not break.
- Their `description` (LLM) fields are prefixed with `DEPRECATED: use
  manage_sandbox(action=...) instead.` so the model prefers the consolidated tool.
- Their human label may be suffixed `(deprecated)`.
- Removal is scheduled for the next release after a one-version window, at which
  point the net tool count drops by two.

### Why `destroy_sandbox` stays separate

Destruction is irreversible. Keeping it as a distinct, explicitly named tool
(rather than `manage_sandbox(action=destroy)`) reduces the chance that a planning
LLM deletes a sandbox while reaching for a reversible state change. This is a
deliberate safety-over-symmetry choice.

## 2. Configurable execution timeout

Add an optional `timeout` parameter (integer seconds) to `run_code`,
`run_command`, and `git_clone`.

- Default: unchanged behavior.
  - `run_code` / `run_command`: default to the existing `EXECUTION_TIMEOUT`
    (120s) when `timeout` is omitted.
  - `git_clone`: default to current behavior (SDK default, no explicit timeout).
- Clamp: a module-level `MAX_EXECUTION_TIMEOUT` (e.g. 600s) bounds user input to
  protect the worker; values above the cap are clamped, values below 1 are
  rejected/normalized.
- Pass-through:
  - `run_code`: `sandbox.process.code_run(code, timeout=resolved_timeout)`.
  - `run_command`: `sandbox.process.exec(command, cwd=..., env=...,
    timeout=resolved_timeout)`.
  - `git_clone`: since `Git.clone` has no timeout argument, enforce the bound at
    the plugin level — run the clone and surface a clear, timeout-aware error
    message if it exceeds the budget. Implementation detail (thread/async guard)
    is left to the implementer; the requirement is a clear timeout error rather
    than an indefinite hang.
- YAML: add `timeout` as an optional number parameter with a description that
  explains the default and the maximum, and notes that long installs/builds may
  need a higher value.

## 3. Correct proxied preview for private sandboxes

Today `rewrite_preview_url` strips the token, which breaks private-sandbox
previews behind the proxy. Change `get_preview_url` so that, when
`preview_proxy_domain` is configured:

- Determine whether a token is required. `get_preview_link(port)` returns a
  `token`; treat a non-empty token as "private/token-required".
- When a token is required AND a proxy domain is set, do ONE of the following
  (implementer choice, in priority order):
  1. Propagate the token through the proxied URL as a query parameter that the
     Nginx `/preview/` block forwards as the `x-daytona-preview-token` header; OR
  2. If propagation is not configured, return the proxied URL **and** an explicit
     warning in the JSON/text contract that the sandbox is private and the proxy
     must inject the preview token, plus a hint to set the sandbox `public=true`.
- When no token is required (public sandbox), behavior is unchanged.
- Keep `include_token=false` as the default; never leak the token into the
  default human-facing text.
- Document in the tool description and README that proxied previews of private
  sandboxes require token propagation at the proxy, and that the simplest path is
  to create the sandbox with `public=true`.

## 4. Memory-bounded `read_file`

Avoid downloading an entire large file just to display a head.

- Before downloading, call `fs.get_file_info(remote_path)` to obtain `size`.
- Define a guard `READ_FULL_DOWNLOAD_LIMIT` (e.g. 5 MB). If `size` exceeds the
  guard AND `size > max_bytes`:
  - Do not download the full file. Return a clear result indicating the file is
    too large to fully retrieve via `read_file`, report `size_bytes`, set
    `truncated=true`, and instruct the agent to use `download_file` for the full
    artifact (or raise `max_bytes` deliberately).
  - Where the daemon supports a partial fetch path, retrieve only the requested
    head; otherwise, return the size-only result above. (SDK `0.187.0` exposes no
    range read, so the conservative behavior is the size-guard refusal.)
- For files within the guard, behavior is unchanged: download, truncate to
  `max_bytes`, decode UTF-8 with `errors="replace"`.
- Keep the existing 100 MB hard cap as the absolute upper bound.

## 5. Documentation accuracy

- README "Quick one-off execution": state that `run_code` / `run_command` use the
  conversation's active sandbox when `sandbox_id` is omitted and only create an
  ephemeral sandbox when no active sandbox exists.
- README: document `manage_sandbox`, mark the three lifecycle tools deprecated,
  document the `timeout` parameters, and document the proxy/private-sandbox
  preview requirement.

## Tool surface after this change

Existing (19): `create_sandbox`, `run_code`, `run_command`, `start_service`,
`get_service_logs`, `start_sandbox`*, `stop_sandbox`*, `archive_sandbox`*,
`upload_file`, `download_file`, `read_file`, `write_file`, `list_files`,
`search_files`, `find_in_files`, `git_clone`, `get_preview_url`,
`list_sandboxes`, `destroy_sandbox`.

Added (1): `manage_sandbox`.

`*` deprecated this release; scheduled for removal next release.

## Risks

- **Transient tool-count increase.** This release adds `manage_sandbox` while
  keeping the deprecated trio, temporarily raising the count to 20. The intended
  reduction lands when the deprecated tools are removed next release. Accepted to
  preserve backward compatibility.
- **Git clone timeout enforcement.** Because the SDK lacks a clone timeout, the
  plugin-level guard must be implemented carefully to avoid leaking threads or
  leaving partial clones; on timeout, report state clearly.
- **Proxy token propagation depends on infrastructure.** Option (1) in section 3
  requires the Nginx `/preview/` block to forward the token header. If the
  infrastructure is not updated, the implementation must fall back to option (2)
  (warn) so the contract never silently fails.
- **Backward compatibility.** All additions are optional/additive; existing tool
  names, parameters, and default behaviors are unchanged.
