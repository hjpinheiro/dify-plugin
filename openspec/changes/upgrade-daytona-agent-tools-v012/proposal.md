# Proposal: Upgrade Daytona Dify Agent Tools v0.0.12

## Intent

Improve agent reliability, cost control, and correctness of the Daytona Dify
plugin by acting on the findings of an API-level audit against the Daytona Python
SDK `0.187.0`. The audit confirmed that every SDK call in the v0.0.10 plugin is
**correct**; this change therefore targets **tool ergonomics**, **execution
limits**, and **preview correctness**, not bug fixes to SDK usage.

The v0.0.9–v0.0.10 line delivered transparent sandbox reactivation, active
sandbox memory, background services, lifecycle tools, chart metadata, workflow
variables, the packaging safety gate, and the preview proxy domain. This release
focuses on the consolidation and robustness work that was explicitly deferred in
v0.0.9 ("Tool consolidation/renaming ... tracked as a future, separately
versioned change").

## Motivation

- **Lifecycle tool sprawl hurts agent tool-selection.** `start_sandbox`,
  `stop_sandbox`, and `archive_sandbox` are near-identical wrappers that differ
  only by the SDK method they call. Three almost-duplicate tools inflate the
  agent's tool list, increase prompt tokens, and raise the probability of
  wrong-tool selection in ReAct/Function-Calling loops.
- **Execution timeout is hardcoded at 120s.** `run_code` and `run_command` use a
  fixed `EXECUTION_TIMEOUT = 120`, and `git_clone` relies on the SDK default.
  Common real workloads — `pip install` of large wheels, `pytest` suites, builds,
  and clones of large repositories — routinely exceed 120s and fail with an
  opaque timeout, with no way for the agent or workflow author to extend it.
- **Preview proxy assumes public sandboxes.** When `preview_proxy_domain` is set,
  `get_preview_url` rewrites the URL to `https://{proxy}/preview/{subdomain}/`
  and drops the Daytona preview `token`. For a **private** sandbox the Daytona
  edge requires that token (header `x-daytona-preview-token`), so proxied
  previews of private sandboxes fail silently. The contract does not make this
  requirement explicit.
- **`read_file` pulls the whole file into memory to show a slice.** It calls
  `fs.download_file` for the entire file (bounded only by the 100 MB cap) and
  then truncates to `max_bytes` (default 50 KB). Reading a small head of a large
  file downloads the entire file into the plugin-daemon process.
- **Docs overstate ephemeral behavior.** The README "Quick one-off execution"
  section implies that omitting `sandbox_id` always creates an ephemeral sandbox.
  In practice `run_code` / `run_command` first resolve the conversation's active
  sandbox (`recall_sandbox`) and only fall back to ephemeral when none exists.

## Scope

This change includes:

- Add a consolidated `manage_sandbox` tool taking an `action`
  (`start` | `stop` | `archive`) and an optional `sandbox_id`, replacing the
  three separate lifecycle tools as the recommended interface.
- Deprecate (but keep registered for one release) `start_sandbox`,
  `stop_sandbox`, and `archive_sandbox` so existing agent configurations do not
  break; mark them clearly as deprecated in their LLM descriptions and route to
  `manage_sandbox`.
- Keep `destroy_sandbox` as a separate, explicitly named tool because its effect
  is irreversible; it is intentionally NOT folded into `manage_sandbox`.
- Add an optional `timeout` parameter (seconds, clamped to a safe maximum) to
  `run_code`, `run_command`, and `git_clone`, defaulting to today's behavior.
- Make proxied preview URLs correct for private sandboxes in `get_preview_url`:
  document the token requirement, and either propagate the token through the
  proxied URL (query parameter / documented header) or surface a clear warning
  when a private sandbox is proxied without a token.
- Make `read_file` memory-bounded by checking `fs.get_file_info` first and
  refusing to fully download files above a configurable guard, while still
  returning the requested head.
- Update the README to describe the real ephemeral/active-sandbox resolution
  order, the consolidated lifecycle tool, the new `timeout` parameters, and the
  proxy/private-sandbox preview requirement.
- Bump version to `0.0.12`, update provider/manifest tool lists, and re-run the
  packaging safety gate.

## Out Of Scope

- Removing the deprecated `start_sandbox` / `stop_sandbox` / `archive_sandbox`
  tools (scheduled for the next release after a one-version deprecation window).
- Folding `destroy_sandbox` into `manage_sandbox`.
- Merging the file-discovery tools (`list_files`, `search_files`, `find_in_files`)
  or the read/write vs upload/download pairs; each maps 1:1 to a distinct SDK
  call and output contract and stays as-is.
- Range/streaming reads (the SDK `0.187.0` has no partial-read primitive).
- Converting the provider into a Dify Agent Strategy plugin.
- Deploying or changing the Nginx `/preview/` proxy itself (infrastructure).

## Success Criteria

- An agent can start, stop, and archive a sandbox through a single
  `manage_sandbox` tool, and agents still using the old lifecycle tools keep
  working in this release.
- `run_code`, `run_command`, and `git_clone` accept an explicit `timeout` that
  raises the bound for long operations, clamped to a safe maximum, with the
  default preserving current behavior.
- A proxied preview of a private sandbox either works (token propagated) or fails
  with a clear, actionable message; the tool contract documents the requirement.
- Reading the head of a large file no longer downloads the entire file when a
  size guard is exceeded, and the tool reports that the file was too large to
  fully retrieve.
- The README accurately documents the ephemeral/active-sandbox resolution order.
- The package builds through the safety gate at version `0.0.12` with a tool list
  that includes `manage_sandbox` and preserves all existing tool names.

## References

- API audit against Daytona Python SDK `0.187.0` (local inspection):
  `Sandbox.start/stop/archive`, `Sandbox.wait_for_sandbox_start`,
  `Process.code_run(code, params, timeout)`, `Process.exec(command, cwd, env,
  timeout)`, `Git.clone(...)`, `Sandbox.get_preview_link(port) -> PortPreviewUrl
  (url, token)`, `FileSystem.get_file_info`, `FileSystem.download_file`.
- Daytona preview docs: private sandbox previews require the
  `x-daytona-preview-token` header.
- Prior changes `upgrade-daytona-agent-tools-v006` and
  `upgrade-daytona-agent-tools-v009`, and current plugin code at v0.0.10.
