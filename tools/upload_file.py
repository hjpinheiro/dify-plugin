from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.file.file import File

from _client import MAX_FILE_SIZE, build_client, daytona_operation, get_sandbox, resolve_sandbox_id


class UploadFileTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        sandbox_id = resolve_sandbox_id(self, tool_parameters)

        remote_path = tool_parameters.get("remote_path")
        if not remote_path:
            raise ValueError("remote_path is required")

        file = tool_parameters.get("file")
        if not file:
            raise ValueError("file is required")
        if not isinstance(file, File):
            raise ValueError(f"Expected file parameter to be a File, got {type(file).__name__}")

        file_size = file.size
        if file_size is None:
            blob = file.blob
            file_size = len(blob)
        else:
            blob = None

        if file_size > MAX_FILE_SIZE:
            raise ValueError(
                f"File size ({file_size} bytes) exceeds maximum allowed size "
                f"({MAX_FILE_SIZE} bytes)."
            )

        if blob is None:
            blob = file.blob

        daytona = build_client(self.runtime.credentials)
        sandbox = get_sandbox(daytona, sandbox_id)

        with daytona_operation("uploading file"):
            sandbox.fs.upload_file(blob, remote_path)

        yield self.create_json_message({
            "success": True,
            "sandbox_id": sandbox_id,
            "remote_path": remote_path,
            "size_bytes": len(blob),
        })
        yield self.create_text_message(f"Uploaded {file.filename or 'file'} ({len(blob)} bytes) to {remote_path}")