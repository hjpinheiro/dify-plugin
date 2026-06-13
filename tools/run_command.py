import json
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from daytona import CreateSandboxFromSnapshotParams

from _client import EXECUTION_TIMEOUT, build_client, daytona_operation, get_sandbox, remember_sandbox, recall_sandbox


class RunCommandTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        daytona = build_client(self.runtime.credentials)

        explicit_id = tool_parameters.get("sandbox_id") or ""
        stored_id = recall_sandbox(self) if not explicit_id else ""
        sandbox_id = explicit_id or stored_id
        ephemeral = not sandbox_id

        command = tool_parameters["command"]
        cwd = tool_parameters.get("cwd") or None

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

        try:
            with daytona_operation("executing command"):
                response = sandbox.process.exec(
                    command, cwd=cwd, env=env_vars, timeout=EXECUTION_TIMEOUT
                )

            yield self.create_text_message(response.result or "(no output)")

            yield self.create_json_message({
                "exit_code": response.exit_code,
                "output": response.result or "",
                "sandbox_id": sandbox.id,
            })

            yield self.create_variable_message("sandbox_id", sandbox.id)
            yield self.create_variable_message("exit_code", response.exit_code)
        finally:
            if ephemeral:
                try:
                    sandbox.delete()
                except Exception:
                    pass

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
