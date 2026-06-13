# Tasks

## 1. Consolidated lifecycle tool `manage_sandbox`

- [x] 1.1 Add `tools/manage_sandbox.py` taking `action` (`start`|`stop`|`archive`)
      and optional `sandbox_id` resolved via `resolve_sandbox_id`.
- [x] 1.2 Use `daytona.get(sandbox_id)` directly (no `auto_start`) so `stop` and
      `archive` do not pre-start the sandbox; for `start`, call `sandbox.start()`
      then `wait_for_sandbox_start()`.
- [x] 1.3 Re-fetch the sandbox and return JSON (`sandbox_id`, `action`, `state`)
      plus a concise text summary.
- [x] 1.4 Reject unknown `action` values with a clear error.
- [x] 1.5 Add `tools/manage_sandbox.yaml` with an `action` select parameter and an
      optional `sandbox_id`, and an LLM description covering all three actions.
- [x] 1.6 Register `manage_sandbox` in `provider/daytona.yaml`.

## 2. Deprecate the separate lifecycle tools (backward compatible)

- [x] 2.1 Prefix the `description` of `start_sandbox`, `stop_sandbox`, and
       `archive_sandbox` with `DEPRECATED: use manage_sandbox(action=...) instead.`
- [x] 2.2 Suffix their human labels with `(deprecated)` where labels exist.
- [x] 2.3 Keep all three tools registered and functional in this release.
- [x] 2.4 Add a code comment and README note that removal is scheduled for the
       next release after a one-version deprecation window.
- [x] 2.5 Confirm `destroy_sandbox` remains a separate tool and is NOT added to
       `manage_sandbox`.

### Removed in v0.0.13
- [x] 2.6 Delete `tools/start_sandbox.py`, `tools/start_sandbox.yaml` — removed.
- [x] 2.7 Delete `tools/stop_sandbox.py`, `tools/stop_sandbox.yaml` — removed.
- [x] 2.8 Delete `tools/archive_sandbox.py`, `tools/archive_sandbox.yaml` — removed.
- [x] 2.9 Remove all 3 entries from `provider/daytona.yaml` — removed.

## 3. Configurable execution timeout

- [x] 3.1 Add `MAX_EXECUTION_TIMEOUT` (e.g. 600) to `_client.py` and a helper to
      resolve/clamp a `timeout` parameter against the existing default.
- [x] 3.2 `run_code`: accept optional `timeout`, pass it to
      `process.code_run(code, timeout=...)`, defaulting to `EXECUTION_TIMEOUT`.
- [x] 3.3 `run_command`: accept optional `timeout`, pass it to
      `process.exec(command, cwd=..., env=..., timeout=...)`.
- [x] 3.4 `git_clone`: accept optional `timeout`; since `Git.clone` has no timeout
      argument, enforce the bound at the plugin level and surface a clear,
      timeout-aware error instead of hanging indefinitely.
- [x] 3.5 Add `timeout` (optional number) to `run_code.yaml`, `run_command.yaml`,
      and `git_clone.yaml`, documenting the default and the maximum.
- [x] 3.6 Confirm omitting `timeout` preserves the current behavior exactly.

## 4. Correct proxied preview for private sandboxes

- [x] 4.1 In `get_preview_url.py`, detect a token-required (private) preview from
      a non-empty `preview.token`.
- [x] 4.2 When `preview_proxy_domain` is set and the preview is private, either
      propagate the token through the proxied URL (query param forwarded by the
      proxy as `x-daytona-preview-token`) OR include an explicit warning in the
      JSON and text contract that the proxy must inject the token.
- [x] 4.3 Add a hint to set the sandbox `public=true` for the simplest proxied
      preview path.
- [x] 4.4 Keep `include_token=false` as the default and never leak the token into
      the default human-facing text.
- [x] 4.5 Update `get_preview_url.yaml` description and README to document the
      proxy/private-sandbox token requirement.
- [x] 4.6 Confirm public-sandbox preview behavior is unchanged.

## 5. Memory-bounded `read_file`

- [x] 5.1 Add `READ_FULL_DOWNLOAD_LIMIT` (e.g. 5 MB) to `read_file.py` or
      `_client.py`.
- [x] 5.2 Call `fs.get_file_info(remote_path)` before downloading to obtain size.
- [x] 5.3 When `size` exceeds the guard AND `size > max_bytes`, do not fully
      download; return a clear result with `size_bytes`, `truncated=true`, and a
      hint to use `download_file` or raise `max_bytes`.
- [x] 5.4 For files within the guard, preserve current behavior (download,
      truncate to `max_bytes`, UTF-8 decode with `errors="replace"`).
- [x] 5.5 Keep the 100 MB hard cap as the absolute upper bound.

## 6. Documentation

- [x] 6.1 Update README "Quick one-off execution" to describe the
      active-sandbox-first resolution order and ephemeral fallback.
- [x] 6.2 Document `manage_sandbox` and mark the three lifecycle tools deprecated
      in the README and the Tool Reference table.
- [x] 6.3 Document the new `timeout` parameters for `run_code`, `run_command`, and
      `git_clone`.
- [x] 6.4 Document the proxy/private-sandbox preview requirement.

## 7. Packaging and versioning

- [x] 7.1 Bump `manifest.yaml` top-level `version` and `meta.version` to `0.0.12`.
- [x] 7.2 Update the provider tool list and any tool-count references.
- [x] 7.3 Run `package.py` so the safety gate validates YAML, version equality,
      tool registration, and files-only archive.
- [x] 7.4 Confirm the package includes `manage_sandbox.py` / `.yaml` and all
      existing tools.

## 8. Verification

- [x] 8.1 Run YAML parse validation for all YAML files.
- [x] 8.2 Run Python syntax/import checks for the provider and all tool modules.
- [x] 8.3 Cross-check the provider tool list against tool YAML and Python files.
- [x] 8.4 Run package generation and confirm the safety gate passes.
- [x] 8.5 If Daytona credentials are available, smoke-test: `manage_sandbox`
      start/stop/archive; `run_command` with an extended `timeout`; a proxied
      preview of a private sandbox; and `read_file` against an oversized file.
- [x] 8.6 If Dify is available, install the package and confirm the tool list
      includes `manage_sandbox`, the deprecated tools still work, and agents can
      manage sandbox lifecycle through the consolidated tool.
