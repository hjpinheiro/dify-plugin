from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _client import MAX_FILE_SIZE, build_client, daytona_operation, get_sandbox


class WriteFileTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        sandbox_id = tool_parameters.get("sandbox_id")
        if not sandbox_id:
            raise ValueError("sandbox_id is required")

        remote_path = tool_parameters.get("remote_path")
        if not remote_path:
            raise ValueError("remote_path is required")

        content = tool_parameters.get("content")
        if content is None:
            raise ValueError("content is required")

        if not isinstance(content, (str, bytes)):
            content = str(content)
        content_bytes = content.encode("utf-8") if isinstance(content, str) else content
        if len(content_bytes) > MAX_FILE_SIZE:
            raise ValueError(
                f"Content size ({len(content_bytes)} bytes) exceeds maximum allowed size "
                f"({MAX_FILE_SIZE} bytes)."
            )

        daytona = build_client(self.runtime.credentials)
        sandbox = get_sandbox(daytona, sandbox_id)

        with daytona_operation("writing file"):
            sandbox.fs.upload_file(content_bytes, remote_path)

        yield self.create_json_message({
            "success": True,
            "sandbox_id": sandbox_id,
            "remote_path": remote_path,
            "size_bytes": len(content_bytes),
        })
        yield self.create_text_message(f"Wrote {len(content_bytes)} bytes to {remote_path}")
