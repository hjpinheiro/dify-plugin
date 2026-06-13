# Tasks: Upgrade Daytona Dify Agent Tools v0.11

## 1. Stateful Python Interpreter

- [ ] 1.1 Add `stateful` boolean parameter to `tools/run_code.yaml` (default: true).
- [ ] 1.2 In `tools/run_code.py`, when `stateful=True` and `language="python"`,
      use `sandbox.code_interpreter.run_code(code, timeout=...)` instead of
      `sandbox.process.code_run(code, timeout=...)`.
- [ ] 1.3 Extract `stdout`, `stderr`, and `error` from `ExecutionResult`. When
      `error` is not None, include `name`, `value`, and `traceback` in the JSON
      response and surface a clear error text message.
- [ ] 1.4 When `stateful=False` or language is TS/JS, keep existing
      `process.code_run` path with chart artifact extraction — unchanged.
- [ ] 1.5 Bump manifest.yaml and meta.version to `0.0.11`.

## 2. Real-time Output Streaming for run_command

- [ ] 2.1 Add `stream` boolean parameter to `tools/run_command.yaml` (default: false).
- [ ] 2.2 In `tools/run_command.py`, when `stream=True`, use session-based async
      execution: create session, run with `var_async=True`, poll
      `get_session_command_logs` every 2 seconds yielding new chunks as
      `create_text_message`.
- [ ] 2.3 Detect process completion via `get_session(session_id)` command state
      (exit_code field). On completion, yield final JSON with exit_code and full
      output summary.
- [ ] 2.4 Cap total streaming time at `EXECUTION_TIMEOUT` (120s). On timeout,
      yield a timeout warning message.
- [ ] 2.5 When `stream=False` (default), use existing `process.exec` path —
      unchanged.

## 3. Zero-Copy File Injection

- [ ] 3.1 Add optional `input_files` parameter (type: files, multi) to
      `tools/run_code.yaml` and `tools/run_command.yaml`.
- [ ] 3.2 In both `run_code.py` and `run_command.py`, before execution, if
      `input_files` is provided, upload each file to
      `/home/daytona/workspace/{filename}` via `sandbox.fs.upload_file`.
- [ ] 3.3 Include uploaded file paths in the JSON response for agent awareness.
- [ ] 3.4 Validate file size against `MAX_FILE_SIZE` before upload.

## 4. Web Port Discovery & Auto-Expose

- [ ] 4.1 Create `tools/auto_expose.py` and `tools/auto_expose.yaml`.
- [ ] 4.2 Run a Python port-scanning snippet inside the sandbox via
      `run_code(code_interpreter)` to discover listening TCP ports in range
      1000-10000.
- [ ] 4.3 For each discovered port, call `sandbox.get_preview_link(port)` and
      apply proxy-domain rewriting (reuse `rewrite_preview_url` from
      `get_preview_url.py`).
- [ ] 4.4 Return JSON with array of `{port, url}` and a text summary.
- [ ] 4.5 Register the tool in `provider/daytona.yaml`.

## 5. Final Integration

- [ ] 5.1 Run `package.py` validation gate to confirm all YAML parses, versions
      match, and all tools have matching `.yaml` + `.py` files.
- [ ] 5.2 Update `README.md` tool table with new parameters and `auto_expose`.
- [ ] 5.3 Build `.difypkg` and verify archive contains no directory entries.
