import json
import time
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from daytona import CreateSandboxFromSnapshotParams, SessionExecuteRequest

from _client import (
    EXECUTION_TIMEOUT,
    MAX_FILE_SIZE,
    build_client,
    daytona_operation,
    get_sandbox,
    remember_sandbox,
    resolve_timeout,
    try_resolve_sandbox_id,
)


class RunCommandTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        daytona = build_client(self.runtime.credentials)

        sandbox_id = try_resolve_sandbox_id(self, tool_parameters)
        ephemeral = not sandbox_id

        command = tool_parameters["command"]
        cwd = tool_parameters.get("cwd") or None
        stream = bool(tool_parameters.get("stream", False))
        timeout = resolve_timeout(tool_parameters.get("timeout")) or EXECUTION_TIMEOUT

        env_vars = self._parse_env_vars(tool_parameters.get("env_vars"))

        if sandbox_id:
            sandbox = get_sandbox(daytona, sandbox_id)
            remember_sandbox(self, sandbox.id)
        else:
            with daytona_operation("creating ephemeral sandbox"):
                sandbox = daytona.create(CreateSandboxFromSnapshotParams(
                    ephemeral=True,
                    auto_stop_interval=5,
                ))

        uploaded_paths = self._inject_files(sandbox, tool_parameters)

        try:
            if stream:
                yield from self._stream_execution(
                    sandbox, command, cwd, env_vars, uploaded_paths, timeout,
                )
            else:
                yield from self._blocking_execution(
                    sandbox, command, cwd, env_vars, uploaded_paths, timeout,
                )
        finally:
            if ephemeral:
                try:
                    sandbox.delete()
                except Exception:
                    pass

    def _inject_files(self, sandbox, tool_parameters: dict[str, Any]) -> list[str]:
        """Upload input_files to the sandbox workspace. Returns list of uploaded paths."""
        files = tool_parameters.get("input_files")
        if not files:
            return []
        if not isinstance(files, list):
            files = [files]

        uploaded = []
        for f in files:
            if not hasattr(f, "blob") or not hasattr(f, "filename"):
                continue
            blob = f.blob
            if len(blob) > MAX_FILE_SIZE:
                raise ValueError(
                    f"File '{f.filename}' size ({len(blob)} bytes) exceeds maximum "
                    f"allowed size ({MAX_FILE_SIZE} bytes)."
                )
            remote_path = f"/home/daytona/workspace/{f.filename}"
            with daytona_operation(f"uploading {f.filename}"):
                sandbox.fs.upload_file(blob, remote_path)
            uploaded.append(remote_path)
        return uploaded

    def _stream_execution(
        self,
        sandbox: Any,
        command: str,
        cwd: str | None,
        env_vars: dict[str, str] | None,
        uploaded_paths: list[str],
        timeout: int = EXECUTION_TIMEOUT,
    ) -> Generator[ToolInvokeMessage]:
        session_id = f"cmd-{int(time.time())}"

        try:
            with daytona_operation("creating session"):
                sandbox.process.create_session(session_id)
        except Exception:
            pass

        with daytona_operation("executing command (streaming)"):
            req = SessionExecuteRequest(
                command=command,
                var_async=True,
            )
            if cwd:
                req.cwd = cwd
            if env_vars:
                req.env = env_vars
            response = sandbox.process.execute_session_command(session_id, req)

        cmd_id = getattr(response, "cmd_id", None)
        if not cmd_id:
            yield self.create_text_message(
                "(command failed to start — no cmd_id returned)"
            )
            return

        stdout_offset = 0
        stderr_offset = 0
        start = time.time()

        while True:
            if time.time() - start > timeout:
                yield self.create_text_message(
                    f"(timeout: command exceeded {timeout}s "
                    "and has not completed)",
                )
                break

            time.sleep(2)

            with daytona_operation("fetching command logs"):
                logs = sandbox.process.get_session_command_logs(
                    session_id, cmd_id,
                )

            stdout = getattr(logs, "stdout", "") or ""
            stderr = getattr(logs, "stderr", "") or ""

            if len(stdout) > stdout_offset:
                chunk = stdout[stdout_offset:]
                stdout_offset = len(stdout)
                yield self.create_text_message(chunk)

            if len(stderr) > stderr_offset:
                chunk = stderr[stderr_offset:]
                stderr_offset = len(stderr)
                yield self.create_text_message(chunk)

            with daytona_operation("checking command status"):
                session = sandbox.process.get_session(session_id)
                commands = getattr(session, "commands", None) or []

            done = False
            exit_code = None

            if commands:
                cmd = commands[-1]
                raw = getattr(cmd, "exit_code", None)
                if raw is not None:
                    try:
                        exit_code = int(raw)
                    except (ValueError, TypeError):
                        exit_code = raw
                    done = True

            if done:
                full_out = (getattr(logs, "stdout", "") or "") + \
                           (getattr(logs, "stderr", "") or "")

                if len(stdout) > stdout_offset:
                    yield self.create_text_message(stdout[stdout_offset:])
                    stdout_offset = len(stdout)
                if len(stderr) > stderr_offset:
                    yield self.create_text_message(stderr[stderr_offset:])
                    stderr_offset = len(stderr)

                yield self.create_json_message({
                    "exit_code": exit_code,
                    "output": full_out,
                    "sandbox_id": sandbox.id,
                    "uploaded_files": uploaded_paths,
                })

                yield self.create_variable_message(
                    "exit_code", str(exit_code),
                )
                yield self.create_variable_message(
                    "sandbox_id", sandbox.id,
                )
                break

        try:
            sandbox.process.delete_session(session_id)
        except Exception:
            pass

    def _blocking_execution(
        self,
        sandbox: Any,
        command: str,
        cwd: str | None,
        env_vars: dict[str, str] | None,
        uploaded_paths: list[str],
        timeout: int = EXECUTION_TIMEOUT,
    ) -> Generator[ToolInvokeMessage]:
        with daytona_operation("executing command"):
            response = sandbox.process.exec(
                command, cwd=cwd, env=env_vars, timeout=timeout,
            )

        yield self.create_text_message(response.result or "(no output)")

        yield self.create_json_message({
            "exit_code": response.exit_code,
            "output": response.result or "",
            "sandbox_id": sandbox.id,
            "uploaded_files": uploaded_paths,
        })

        yield self.create_variable_message("sandbox_id", sandbox.id)
        yield self.create_variable_message("exit_code", response.exit_code)

    @staticmethod
    def _parse_env_vars(raw: Any) -> dict[str, str] | None:
        if not raw:
            return None
        if isinstance(raw, dict):
            return {str(k): str(v) for k, v in raw.items()}
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError) as e:
            raise ValueError(f"env_vars must be a JSON object string: {e}")
        if not isinstance(parsed, dict):
            raise ValueError("env_vars must be a JSON object")
        return {str(k): str(v) for k, v in parsed.items()}
