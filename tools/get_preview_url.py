from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _client import build_client, daytona_operation, get_sandbox


class GetPreviewUrlTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        sandbox_id = tool_parameters.get("sandbox_id")
        if not sandbox_id:
            raise ValueError("sandbox_id is required")

        port = tool_parameters.get("port")
        if port is None or port == "":
            raise ValueError("port is required")
        port = int(port)
        if not (3000 <= port <= 9999):
            raise ValueError(f"Port must be between 3000 and 9999, got {port}")

        include_token = tool_parameters.get("include_token", False)

        daytona = build_client(self.runtime.credentials)
        sandbox = get_sandbox(daytona, sandbox_id)

        with daytona_operation("getting preview URL"):
            preview = sandbox.get_preview_link(port)

        yield self.create_link_message(preview.url)

        json_result: dict[str, Any] = {
            "url": preview.url,
            "port": port,
            "sandbox_id": sandbox_id,
        }
        if include_token:
            json_result["token"] = preview.token
        else:
            json_result["requires_token"] = True

        yield self.create_json_message(json_result)
        yield self.create_text_message(f"Preview URL for port {port}: {preview.url}")
