## 1. Shared Helpers

- [ ] 1.1 Add a deterministic shared command-session ID helper derived from
      `conversation_id` and `sandbox_id`.
- [ ] 1.2 Add a helper that gets or creates the shared Daytona command session
      and recreates it when missing.
- [ ] 1.3 Add a shell-command composition helper that applies `cwd` and
      `env_vars` safely with quoting.
- [ ] 1.4 Add a shared text-file injection helper for `input_text_files` that
      writes files under `/home/daytona/workspace/` and rejects path traversal.

## 2. Deterministic Sandbox Resolution

- [ ] 2.1 Remove `find_any_sandbox()` fallback from `resolve_sandbox_id()`.
- [ ] 2.2 Remove `find_any_sandbox()` fallback from `try_resolve_sandbox_id()`.
- [ ] 2.3 Confirm `run_code` and `run_command` still create an ephemeral sandbox
      only when no conversation sandbox exists.
- [ ] 2.4 Update sandbox-resolution text/JSON messages so tools no longer imply
      arbitrary unlabeled-sandbox reuse.

## 3. Refactor `run_command`

- [ ] 3.1 Change blocking `run_command` to use
      `execute_session_command(...)` instead of stateless `process.exec(...)`.
- [ ] 3.2 Change streaming `run_command` to use `run_async=True` instead of the
      deprecated `var_async=True` path.
- [ ] 3.3 Stop deleting the shared command session at the end of every call.
- [ ] 3.4 Apply `cwd` and `env_vars` through composed shell commands rather than
      unsupported SDK request fields.
- [ ] 3.5 Add `input_text_files` to `run_command.yaml` with an LLM-facing JSON
      string description and example.
- [ ] 3.6 Ensure `run_command` JSON results include all text-injected file paths
      in `uploaded_files`.

## 4. Fix `start_service`

- [ ] 4.1 Add `env_vars` to `start_service.yaml`.
- [ ] 4.2 Apply `cwd` and `env_vars` in `start_service.py`.
- [ ] 4.3 Use `run_async=True` in the service session request.
- [ ] 4.4 Keep a dedicated service session so daemon processes do not share the
      normal command session.
- [ ] 4.5 When `port` is provided, include preview metadata in the JSON result
      using the shared preview helper.

## 5. Enhance `run_code`

- [ ] 5.1 Add `env_vars` to `run_code.yaml`.
- [ ] 5.2 Pass `envs=...` to `code_interpreter.run_code(...)` in the stateful
      path.
- [ ] 5.3 Pass environment variables to `process.code_run(...)` in the stateless
      path.
- [ ] 5.4 Add `input_text_files` to `run_code.yaml`.
- [ ] 5.5 Inject `input_text_files` into the sandbox workspace before execution.
- [ ] 5.6 Ensure `run_code` JSON results include all injected file paths in
      `uploaded_files`.

## 6. Agent-Safe Output Contract

- [ ] 6.1 Remove `create_log_message` / `finish_log_message` usage from
      `create_sandbox.py`.
- [ ] 6.2 Remove `create_log_message` / `finish_log_message` usage from
      `git_clone.py`.
- [ ] 6.3 Remove `create_log_message` / `finish_log_message` usage from
      `start_service.py`.
- [ ] 6.4 Remove `create_log_message` / `finish_log_message` usage from
      `auto_expose.py`.
- [ ] 6.5 Confirm each of those tools still returns one concise text summary and
      one structured JSON summary.
- [ ] 6.6 Review existing variable outputs and keep only the ones still needed
      for workflow compatibility.

## 7. Signed Preview URLs

- [ ] 7.1 Add a shared preview helper that can return raw preview links or
      signed preview URLs.
- [ ] 7.2 Update `get_preview_url.py` to prefer signed preview URLs for private
      sandboxes.
- [ ] 7.3 Add an optional expiry parameter such as `expires_in_seconds` to
      `get_preview_url.yaml`.
- [ ] 7.4 Preserve query strings when rewriting preview URLs through
      `preview_proxy_domain`.
- [ ] 7.5 Keep raw token exposure explicit and opt-in only.

## 8. Docs, YAML, and Agent Guidance

- [ ] 8.1 Update `README.md` so it documents session-backed `run_command`,
      deterministic sandbox reuse, signed previews, and text-file ingress.
- [ ] 8.2 Update `run_command.yaml`, `run_code.yaml`, `start_service.yaml`, and
      `get_service_logs.yaml` so their LLM descriptions match the real runtime
      behavior.
- [ ] 8.3 Add a new agent guidance file aligned with the current tool surface and
      FunctionCalling-first usage.
- [ ] 8.4 Document the Dify Agent limitation around `file` / `files` parameters
      and the intended text-based workaround.

## 9. Packaging and Verification

- [ ] 9.1 Bump `manifest.yaml` top-level `version` and `meta.version` to
      `0.0.17`.
- [ ] 9.2 Update `provider/daytona.yaml` and any tool reference docs for new
      parameters.
- [ ] 9.3 Run `package.py` and confirm the safety gate passes.
- [ ] 9.4 Run OpenSpec validation for the new change.
- [ ] 9.5 Run YAML parse validation for all tool YAML files and Python syntax
      checks for the affected modules.
- [ ] 9.6 If Daytona credentials are available, smoke-test persistent shell
      state across `run_command` calls, `start_service` with `cwd` / `env_vars`,
      private signed preview URLs, and `input_text_files`.
- [ ] 9.7 If Dify is available, install the package and verify the official
      `langgenius/agent` FunctionCalling strategy can complete a multi-step repo
      workflow without repeated `cd ... && export ...` wrappers.
