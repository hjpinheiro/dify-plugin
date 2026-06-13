# Tasks

## 1. Transparent sandbox reactivation (critical)

- [ ] 1.1 Update `get_sandbox()` in `_client.py` to accept `auto_start=True` and
      `wait=True` keyword arguments.
- [ ] 1.2 Read sandbox state defensively as
      `getattr(sandbox.state, "value", sandbox.state)` and lowercase it.
- [ ] 1.3 When state is `stopped` or `archived` and `auto_start` is true, call
      `sandbox.start()`, then `sandbox.wait_for_sandbox_start()` when `wait`,
      then re-fetch the sandbox handle.
- [ ] 1.4 Raise a clear error when state is `error`, `destroyed`, or `destroying`.
- [ ] 1.5 Wrap the start/wait in `daytona_operation("starting sandbox")`.
- [ ] 1.6 Confirm all execution/file tools (`run_code`, `run_command`,
      `upload_file`, `download_file`, `read_file`, `write_file`, `list_files`,
      `search_files`, `find_in_files`, `git_clone`, `get_preview_url`) get a
      ready-to-use sandbox via the updated helper.
- [ ] 1.7 Add a bounded timeout/error path so a slow archive-restore surfaces a
      clear message instead of hanging.

## 2. Active sandbox memory via session storage

- [ ] 2.1 Add `remember_sandbox(tool, sandbox_id)`, `recall_sandbox(tool)`, and
      `forget_sandbox(tool)` helpers in `_client.py` using
      `tool.session.storage` with key `active_sandbox_id` (bytes-encoded).
- [ ] 2.2 Wrap all storage access so failures are swallowed and treated as
      "no active sandbox" (best-effort).
- [ ] 2.3 Add a `resolve_sandbox_id(tool, tool_parameters)` helper implementing
      the resolution order: explicit param -> stored active id -> clear error.
- [ ] 2.4 Call `remember_sandbox` in `create_sandbox` and in `run_code` /
      `run_command` when a persistent (non-ephemeral) sandbox is used.
- [ ] 2.5 Call `forget_sandbox` in `destroy_sandbox` when the destroyed id
      matches the stored active id.
- [ ] 2.6 Update tools that require a sandbox to use `resolve_sandbox_id` instead
      of reading `sandbox_id` directly, keeping `sandbox_id` optional where the
      active sandbox can be used.
- [ ] 2.7 Never store credentials in session storage; only the sandbox id.
- [ ] 2.8 Update affected tool YAML descriptions to say `sandbox_id` is optional
      and defaults to the conversation's active sandbox when omitted.

## 3. Background execution and start_service

- [ ] 3.1 Add `tools/start_service.py` that resolves the sandbox, creates or
      reuses a session, and runs the command with
      `SessionExecuteRequest(command=..., var_async=True)`.
- [ ] 3.2 Return JSON including `sandbox_id`, `session_id`, `cmd_id`, and a hint
      to call `get_preview_url` for the service port.
- [ ] 3.3 Optionally read a short bounded window of early logs via
      `get_session_command_logs` to surface startup errors, then stop.
- [ ] 3.4 Add `tools/start_service.yaml` with an LLM description covering the
      canonical flow: start a long-running service in the background, then get
      its preview URL; include a `port` hint parameter and optional `session_id`.
- [ ] 3.5 Add a bounded log-retrieval capability (new tool or parameter) to fetch
      later logs by `session_id`/`cmd_id`, clamped to a safe byte/line budget.
- [ ] 3.6 Keep `run_command` synchronous and unchanged; do not add implicit
      background behavior to it.
- [ ] 3.7 Register new tool(s) in `provider/daytona.yaml`.

## 4. Sandbox lifecycle tools

- [ ] 4.1 Add `tools/start_sandbox.py` + `.yaml` calling `sandbox.start()` and
      returning new state.
- [ ] 4.2 Add `tools/stop_sandbox.py` + `.yaml` calling `sandbox.stop()` and
      returning new state.
- [ ] 4.3 Add `tools/archive_sandbox.py` + `.yaml` calling `sandbox.archive()`
      and returning new state.
- [ ] 4.4 Each returns JSON (`sandbox_id`, `state`) plus a concise text summary.
- [ ] 4.5 Register the three tools in `provider/daytona.yaml`.
- [ ] 4.6 Ensure lifecycle tools do not auto-start the sandbox via
      `get_sandbox(auto_start=False)` where appropriate (e.g. `start_sandbox`
      manages its own start; `stop_sandbox` must not start it first).

## 5. Chart artifact metadata in run_code

- [ ] 5.1 In `run_code.py`, keep yielding `chart.png` blobs.
- [ ] 5.2 Build a `charts` metadata list with defensive `getattr` for `type` and
      `title` (and other safe fields if present).
- [ ] 5.3 Include `charts` and `charts_count` in the JSON output.
- [ ] 5.4 Do not fail if `artifacts` or `charts` are missing.

## 6. Workflow variable outputs

- [ ] 6.1 Emit `create_variable_message("sandbox_id", ...)` from `create_sandbox`.
- [ ] 6.2 Emit `create_variable_message("sandbox_id", ...)` and
      `create_variable_message("exit_code", ...)` from `run_code` / `run_command`
      for persistent sandboxes.
- [ ] 6.3 Emit `create_variable_message("preview_url", ...)` from
      `get_preview_url`.
- [ ] 6.4 Keep all existing text/json/blob messages so agent behavior is
      unchanged.

## 7. Structured logs for long operations

- [ ] 7.1 Wrap `create_sandbox` creation with `create_log_message` /
      `finish_log_message`.
- [ ] 7.2 Wrap `git_clone` with start/finish log messages.
- [ ] 7.3 Wrap `start_service` startup with start/finish log messages.
- [ ] 7.4 Ensure logs are supplementary and never replace the final result
      messages.

## 8. Packaging safety gate

- [ ] 8.1 Add a YAML parse check to `package.py` covering `manifest.yaml`,
      `provider/*.yaml`, and `tools/*.yaml`; fail the build on any parse error.
- [ ] 8.2 Assert `manifest.yaml` has a top-level `version` and a `meta.version`
      and that they are equal.
- [ ] 8.3 Assert every tool listed in `provider/daytona.yaml` has matching
      `tools/<name>.yaml` and `tools/<name>.py` files.
- [ ] 8.4 Assert the generated zip contains files only (no directory entries).
- [ ] 8.5 Make the packaging script exit non-zero when any assertion fails.

## 9. Documentation and packaging

- [ ] 9.1 Bump `manifest.yaml` top-level `version` and `meta.version` to `0.0.9`
      (validate the file parses after editing).
- [ ] 9.2 Update `README.md` to document new tools (`start_service`,
      `start_sandbox`, `stop_sandbox`, `archive_sandbox`), auto-reactivation
      behavior, active-sandbox defaulting, and chart metadata.
- [ ] 9.3 Update the provider tool list and any tool-count references.
- [ ] 9.4 Generate `daytona.difypkg` using `package.py` (now gated by section 8).
- [ ] 9.5 Verify the package contains files only and includes all new
      YAML/Python files.

## 10. Verification

- [ ] 10.1 Run YAML parse validation for all YAML files.
- [ ] 10.2 Run Python syntax/import checks for the provider and all tool modules.
- [ ] 10.3 Cross-check provider tool list against tool YAML and Python files.
- [ ] 10.4 Run package generation and confirm the safety gate passes.
- [ ] 10.5 If Daytona credentials are available, smoke-test:
      reactivation of a stopped sandbox, `start_service` + `get_preview_url`,
      and the lifecycle tools.
- [ ] 10.6 If Dify is available, install the package and confirm the tool list and
      that an agent can reuse a sandbox across turns without manual `sandbox_id`.
