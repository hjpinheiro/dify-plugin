# Proposal: Upgrade Daytona Dify Agent Tools v0.11

## Intent

Transform the Daytona Dify plugin from a basic sandbox executor into a
high-performance agent execution platform by leveraging the Daytona SDK's
stateful interpreter, streaming callbacks, and direct file injection.

## Motivation

- **Stateless execution kills iterative analysis (critical).** `run_code` uses
  `sandbox.process.code_run()` which launches a fresh process each time.
  Variables, imports, and loaded datasets are lost between turns. Agents cannot
  perform exploratory data analysis, incremental debugging, or multi-step model
  training.

- **No real-time feedback on slow commands.** `run_command` uses blocking
  `process.exec()` with a 120-second wall clock. Long builds (`pip install`,
  `npm install`) appear frozen in the Dify UI, risk timeouts, and give the user
  zero visibility.

- **Multi-step file workflow wastes agent turns.** To process an uploaded CSV,
  the agent must call `upload_file` then `run_code` — two tool round-trips. This
  burns LLM tokens, increases latency, and introduces errors.

- **Manual port guessing is error-prone.** Agents must read server logs, guess
  the listening port, then call `get_preview_url`. The system should detect
  active listeners automatically.

## Scope

This change includes:

- Integrate `sandbox.code_interpreter.run_code()` for stateful Python execution
  with persistent variable namespace across conversation turns.
- Stream stdout/stderr from `run_command` in real-time using session-based async
  execution with bounded log polling.
- Add optional `input_file` parameter to `run_code` and `run_command` that
  auto-uploads a Dify file to the workspace before execution.
- Add `auto_expose` tool that discovers listening TCP ports in the sandbox and
  auto-generates preview URLs with proxy domain rewriting.

## Out Of Scope

- Computer-use / VNC screenshot tools (SDK 0.187.0 `computer_use` only manages
  the VNC daemon; no native screenshot/click/type API — deferred to future
  change when SDK exposes these).
- Converting to an Agent Strategy plugin.
- GPU scheduling, volume management, LSP tools.
- Full Git commit/push workflows.

## Success Criteria

- An agent defines `x = 42` in turn 1 and reads `print(x)` in turn 2 — works
  without error.
- `pip install pandas` streams progress lines to the Dify chat in real-time.
- An agent receives a CSV from the user and runs analysis in a single tool call.
- A started web server is auto-detected and its preview URL returned without
  manual port specification.

## References

- Daytona Python SDK 0.187.0: `sandbox.code_interpreter.run_code(code, context,
  on_stdout, on_stderr, on_error, envs, timeout) -> ExecutionResult(stdout,
  stderr, error)`.
- Daytona Python SDK 0.187.0: `sandbox.process.create_session`,
  `execute_session_command(session_id, SessionExecuteRequest(var_async=True))`,
  `get_session_command_logs(session_id, cmd_id)`.
- Dify Plugin SDK: `ToolLike.create_text_message`, `create_blob_message`,
  `create_json_message`, `create_variable_message`, `create_log_message`.
- Existing plugin v0.0.10 code in `hjpinheiro/dify-plugin`.
