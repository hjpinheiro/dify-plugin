from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _client import MAX_FILE_SIZE, build_client, daytona_operation, get_sandbox, resolve_sandbox_id

DEFAULT_MAX_BYTES = 51200  # 50 KB
READ_FULL_DOWNLOAD_LIMIT = 5 * 1024 * 1024


class ReadFileTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        sandbox_id = resolve_sandbox_id(self, tool_parameters)

        remote_path = tool_parameters.get("remote_path")
        if not remote_path:
            raise ValueError("remote_path is required")

        max_bytes = tool_parameters.get("max_bytes", DEFAULT_MAX_BYTES)
        max_bytes = int(max_bytes) if max_bytes else DEFAULT_MAX_BYTES
        if max_bytes < 1:
            max_bytes = 1
        if max_bytes > MAX_FILE_SIZE:
            max_bytes = MAX_FILE_SIZE

        daytona = build_client(self.runtime.credentials)
        sandbox = get_sandbox(daytona, sandbox_id)

        with daytona_operation("getting file info"):
            info = sandbox.fs.get_file_info(remote_path)
        file_size = info.size or 0

        if file_size > READ_FULL_DOWNLOAD_LIMIT and file_size > max_bytes:
            yield self.create_json_message({
                "sandbox_id": sandbox_id,
                "remote_path": remote_path,
                "content": "",
                "size_bytes": file_size,
                "encoding": "utf-8",
                "truncated": True,
                "oversized": True,
                "hint": (
                    f"File is {file_size} bytes which exceeds the inline read limit ({READ_FULL_DOWNLOAD_LIMIT} bytes). "
                    "Use download_file to retrieve the full file, or increase max_bytes to read more."
                ),
            })
            yield self.create_text_message(
                f"File '{remote_path}' is {file_size} bytes — too large to read inline. "
                f"Use download_file to retrieve it, or increase max_bytes (currently {max_bytes})."
            )
            return

        with daytona_operation("reading file"):
            content_bytes = sandbox.fs.download_file(remote_path)

        if content_bytes is None:
            raise ValueError(f"Could not read '{remote_path}' from sandbox '{sandbox_id}': no content returned")

        total_size = len(content_bytes) if not file_size else file_size

        if total_size > MAX_FILE_SIZE:
            raise ValueError(
                f"File size ({total_size} bytes) exceeds maximum allowed size "
                f"({MAX_FILE_SIZE} bytes)."
            )

        truncated = total_size > max_bytes
        if truncated:
            display_bytes = content_bytes[:max_bytes]
        else:
            display_bytes = content_bytes

        text = display_bytes.decode("utf-8", errors="replace")

        yield self.create_json_message({
            "sandbox_id": sandbox_id,
            "remote_path": remote_path,
            "content": text,
            "size_bytes": total_size,
            "encoding": "utf-8",
            "truncated": truncated,
        })

        if truncated:
            yield self.create_text_message(
                f"Read {max_bytes}/{total_size} bytes from {remote_path} (truncated)"
            )
        else:
            yield self.create_text_message(text)
