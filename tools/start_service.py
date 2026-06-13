import time
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from daytona import SessionExecuteRequest

from _client import build_client, daytona_operation, get_sandbox, remember_sandbox, resolve_sandbox_id


class StartServiceTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        sandbox_id = resolve_sandbox_id(self, tool_parameters)
        command = tool_parameters.get("command")
        if not command:
            raise ValueError("command is required")

        port = tool_parameters.get("port")
        cwd = tool_parameters.get("cwd") or None

        session_id = tool_parameters.get("session_id") or f"svc-{int(time.time())}"

        daytona = build_client(self.runtime.credentials)
        sandbox = get_sandbox(daytona, sandbox_id)

        try:
            with daytona_operation("creating session"):
                sandbox.process.create_session(session_id)
        except Exception:
            pass

        log = self.create_log_message(
            label="Starting Background Service",
            data={"command": command, "session_id": session_id},
            status=ToolInvokeMessage.LogMessage.LogStatus.START,
        )
        yield log

        with daytona_operation("starting background service"):
            req = SessionExecuteRequest(command=command, var_async=True)
            response = sandbox.process.execute_session_command(session_id, req)

        yield self.finish_log_message(log, data={"session_id": session_id, "cmd_id": getattr(response, "cmd_id", None)})

        cmd_id = getattr(response, "cmd_id", None)

        startup_logs = ""
        try:
            with daytona_operation("reading startup logs"):
                logs = sandbox.process.get_session_command_logs(session_id, cmd_id)
                if logs:
                    stdout = getattr(logs, "stdout", "") or ""
                    stderr = getattr(logs, "stderr", "") or ""
                    startup_logs = (stdout + stderr)[:2000]
        except Exception:
            pass

        remember_sandbox(self, sandbox_id)

        json_result: dict[str, Any] = {
            "sandbox_id": sandbox_id,
            "session_id": session_id,
            "cmd_id": cmd_id,
            "command": command,
            "status": "running",
        }
        if port:
            json_result["port"] = int(port)
            json_result["hint"] = f"Call get_preview_url with sandbox_id={sandbox_id} and port={port} to get the public URL."
        if startup_logs:
            json_result["startup_logs"] = startup_logs

        yield self.create_json_message(json_result)
        text_parts = [f"Background service started in session '{session_id}'."]
        if port:
            text_parts.append(f"It should be available on port {port} — use get_preview_url to get the public URL.")
        if startup_logs:
            text_parts.append(f"Startup logs:\n{startup_logs[:500]}")
        yield self.create_text_message(" ".join(text_parts))
