from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _client import build_client, daytona_operation, forget_sandbox, recall_sandbox, resolve_sandbox_id


class DestroySandboxTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        sandbox_id = resolve_sandbox_id(self, tool_parameters)

        daytona = build_client(self.runtime.credentials)
        sandbox = daytona.get(sandbox_id)

        with daytona_operation("destroying sandbox"):
            daytona.delete(sandbox)

        stored = recall_sandbox(self)
        if stored and stored == sandbox_id:
            forget_sandbox(self)

        yield self.create_json_message({
            "success": True,
            "sandbox_id": sandbox_id,
        })
        yield self.create_text_message(f"Sandbox '{sandbox_id}' destroyed.")
