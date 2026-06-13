from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _client import build_client, daytona_operation, get_sandbox, resolve_sandbox_id


class GetServiceLogsTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        sandbox_id = resolve_sandbox_id(self, tool_parameters)
        session_id = tool_parameters.get("session_id")
        if not session_id:
            raise ValueError("session_id is required")

        cmd_id = tool_parameters.get("cmd_id")

        max_bytes = tool_parameters.get("max_bytes", 5000)
        max_bytes = int(max_bytes) if max_bytes else 5000
        if max_bytes > 20000:
            max_bytes = 20000
        if max_bytes < 100:
            max_bytes = 100

        daytona = build_client(self.runtime.credentials)
        sandbox = get_sandbox(daytona, sandbox_id)

        if not cmd_id:
            with daytona_operation("fetching session commands"):
                session = sandbox.process.get_session(session_id)
                commands = getattr(session, "commands", None) or []
                if commands:
                    cmd_id = getattr(commands[-1], "id", None) or getattr(commands[-1], "cmd_id", None)
                if not cmd_id:
                    raise ValueError(
                        f"No commands found in session '{session_id}'. "
                        "Provide cmd_id explicitly."
                    )

        with daytona_operation("reading service logs"):
            logs = sandbox.process.get_session_command_logs(session_id, cmd_id)

        stdout = getattr(logs, "stdout", "") or ""
        stderr = getattr(logs, "stderr", "") or ""
        combined = (stdout + stderr)
        truncated = len(combined) > max_bytes
        combined = combined[:max_bytes]

        yield self.create_json_message({
            "sandbox_id": sandbox_id,
            "session_id": session_id,
            "stdout": stdout[:max_bytes],
            "stderr": stderr[:max_bytes],
            "truncated": truncated,
        })
        yield self.create_text_message(combined if combined else "(no logs yet)")
