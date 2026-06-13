# DEPRECATED: use manage_sandbox(action=archive) instead. Scheduled for removal next release.
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _client import build_client, daytona_operation, resolve_sandbox_id


class ArchiveSandboxTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        sandbox_id = resolve_sandbox_id(self, tool_parameters)

        daytona = build_client(self.runtime.credentials)

        with daytona_operation("archiving sandbox"):
            sandbox = daytona.get(sandbox_id)
            sandbox.archive()
            sandbox = daytona.get(sandbox_id)

        state = getattr(sandbox.state, "value", sandbox.state)

        yield self.create_json_message({
            "sandbox_id": sandbox_id,
            "state": state,
        })
        yield self.create_text_message(f"Sandbox '{sandbox_id}' archived (state: {state}). Use start_sandbox to restore it when needed.")
