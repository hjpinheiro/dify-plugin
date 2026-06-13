from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _client import build_client, daytona_operation, resolve_sandbox_id


VALID_ACTIONS = {"start", "stop", "archive"}


class ManageSandboxTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        action = tool_parameters.get("action", "")
        if action not in VALID_ACTIONS:
            raise ValueError(f"Invalid action '{action}'. Must be one of: {', '.join(sorted(VALID_ACTIONS))}")

        sandbox_id = resolve_sandbox_id(self, tool_parameters)

        daytona = build_client(self.runtime.credentials)

        _op = {"start": "starting", "stop": "stopping", "archive": "archiving"}[action]
        with daytona_operation(f"{_op} sandbox"):
            sandbox = daytona.get(sandbox_id)

            state = getattr(sandbox.state, "value", sandbox.state)
            state = (state or "").lower()
            if state in ("error", "destroyed", "destroying"):
                raise ValueError(f"Sandbox '{sandbox_id}' is in state '{state}' and cannot be managed.")

            if action == "start":
                sandbox.start()
                sandbox.wait_for_sandbox_start()
            elif action == "stop":
                sandbox.stop()
            elif action == "archive":
                sandbox.archive()

            sandbox = daytona.get(sandbox_id)

        state = getattr(sandbox.state, "value", sandbox.state)

        yield self.create_json_message({
            "sandbox_id": sandbox_id,
            "action": action,
            "state": state,
        })
        messages = {
            "start": f"Sandbox '{sandbox_id}' started (state: {state}).",
            "stop": f"Sandbox '{sandbox_id}' stopped (state: {state}). Use manage_sandbox with action=start to resume it later without losing data.",
            "archive": f"Sandbox '{sandbox_id}' archived (state: {state}). Use manage_sandbox with action=start to restore it when needed.",
        }
        yield self.create_text_message(messages[action])
