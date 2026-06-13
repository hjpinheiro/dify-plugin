from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _client import build_client, daytona_operation, get_sandbox


class SearchFilesTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        sandbox_id = tool_parameters.get("sandbox_id")
        if not sandbox_id:
            raise ValueError("sandbox_id is required")

        path = tool_parameters.get("path")
        if not path:
            raise ValueError("path is required")

        pattern = tool_parameters.get("pattern")
        if not pattern:
            raise ValueError("pattern is required")

        daytona = build_client(self.runtime.credentials)
        sandbox = get_sandbox(daytona, sandbox_id)

        max_results = tool_parameters.get("max_results", 50)
        max_results = int(max_results) if max_results else 50
        if max_results > 200:
            max_results = 200
        if max_results < 1:
            max_results = 1

        with daytona_operation("searching files"):
            result = sandbox.fs.search_files(path, pattern)

        files = result.files or []
        total = len(files)
        truncated = total > max_results
        files = files[:max_results]

        yield self.create_json_message({
            "sandbox_id": sandbox_id,
            "path": path,
            "pattern": pattern,
            "files": files,
            "count": len(files),
            "total": total,
            "truncated": truncated,
        })
        summary = f"Found {total} files matching '{pattern}' in {path}"
        if truncated:
            summary += f" (showing first {max_results} of {total})"
        yield self.create_text_message(summary)
