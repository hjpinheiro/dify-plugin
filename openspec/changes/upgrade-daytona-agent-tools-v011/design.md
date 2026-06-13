# Design: Upgrade Daytona Dify Agent Tools v0.11

## Overview

The plugin remains a Dify **tool provider**. All improvements are additive — no
existing tool names, parameters, or default behaviors change. New parameters are
optional with backward-compatible defaults.

## Verified SDK Surface (Daytona 0.187.0)

### CodeInterpreter (stateful)

```python
sandbox.code_interpreter.run_code(
    code: str,
    *,
    context: InterpreterContext | None = None,
    on_stdout: OutputHandler[OutputMessage] | None = None,
    on_stderr: OutputHandler[OutputMessage] | None = None,
    on_error:  OutputHandler[ExecutionError]  | None = None,
    envs: dict[str, str] | None = None,
    timeout: int | None = None,   # default 10 min, 0 = no timeout
) -> ExecutionResult(stdout, stderr, error)
```

- `ExecutionResult.stdout`: str
- `ExecutionResult.stderr`: str
- `ExecutionResult.error`: `ExecutionError(name, value, traceback)` or `None`
- Default context persists variables across calls (like a Jupyter kernel).
- `create_context(cwd)` creates an isolated context; `list_contexts()`,
  `delete_context(ctx)` manage them.

### Process (sessions for streaming)

```python
sandbox.process.create_session(session_id)
sandbox.process.execute_session_command(
    session_id, SessionExecuteRequest(command, var_async=True)
) -> ExecuteResponse
sandbox.process.get_session_command_logs(session_id, cmd_id)
    -> SessionCommandLogs(stdout, stderr)
```

### ComputerUse (VNC daemon only — NOT in scope)

```python
sandbox.computer_use.start() -> ComputerUseStartResponse(message, status)
sandbox.computer_use.stop()
sandbox.computer_use.get_status()
```

No screenshot/click/type methods exist in SDK 0.187.0. Deferred.

## Design Decisions

### 1. Stateful interpreter via `code_interpreter`

`run_code` gains `stateful: bool = True` (YAML default). When `stateful` and
`language == "python"`:

```python
result = sandbox.code_interpreter.run_code(code, timeout=EXECUTION_TIMEOUT)
```

When `stateful=False` or language is TypeScript/JavaScript, fall back to
`sandbox.process.code_run()` (existing behavior, unchanged).

Chart extraction: `code_interpreter.run_code` returns `ExecutionResult` without
`artifacts.charts`. Matplotlib charts must be handled differently — the agent
saves charts to disk (e.g. `plt.savefig('/home/daytona/chart.png')`) and the
plugin auto-detects them. The existing `artifacts.charts` extraction from
`process.code_run` remains for `stateful=False`.

### 2. Streaming via session polling

`run_command` gains `stream: bool = False`. When `stream=True`:

1. Create/reuse a session.
2. Execute with `var_async=True`.
3. Poll `get_session_command_logs` every 2 seconds.
4. Yield new stdout/stderr chunks via `create_text_message`.
5. When exit_code is available (via `get_session`), yield final result.

When `stream=False` (default): existing blocking `process.exec()` — unchanged.

### 3. File injection

Both `run_code` and `run_command` gain optional `input_files` parameter (Dify
file picker, accepts one or more files). Before execution:

```python
for f in input_files:
    sandbox.fs.upload_file(f.blob, f"/home/daytona/workspace/{f.filename}")
```

Then proceed with execution as normal. The workspace path is prepended to `cwd`
or noted in the response so the agent knows where files landed.

### 4. Port discovery

New tool `auto_expose`. Runs a lightweight Python one-liner inside the sandbox:

```python
import socket
ports = []
for port in range(1000, 10000):
    s = socket.socket()
    s.settimeout(0.05)
    if s.connect_ex(('127.0.0.1', port)) == 0:
        ports.append(port)
    s.close()
print(ports)
```

For each discovered port, calls `sandbox.get_preview_link(port)` and applies
proxy-domain rewriting (reusing existing `rewrite_preview_url`). Returns JSON
with all exposed URLs.

Scanning range is 1000–10000 (covers common dev servers: Flask 5000, Django
8000, Vite 5173, React 3000, Streamlit 8501, etc.). Timeout per port is 50ms
(9k ports × 50ms ≈ 7.5s worst case — acceptable for a one-shot scan).

## Backward Compatibility

- `run_code` with no `stateful` param → defaults to `True` (new behavior).
  Agents relying on stateless behavior can pass `stateful=False`.
- `run_command` with no `stream` param → blocking (existing behavior).
- `input_files` is optional — existing calls are unaffected.
- `auto_expose` is a new additive tool.
- All existing tool names and signatures remain valid.
