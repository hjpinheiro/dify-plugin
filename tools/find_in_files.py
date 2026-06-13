from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _client import build_client, daytona_operation, get_sandbox


class FindInFilesTool(Tool):
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

        max_results = tool_parameters.get("max_results", 50)
        max_results = int(max_results) if max_results else 50
        if max_results > 200:
            max_results = 200
        if max_results < 1:
            max_results = 1

        daytona = build_client(self.runtime.credentials)
        sandbox = get_sandbox(daytona, sandbox_id)

        with daytona_operation("searching file contents"):
            matches = sandbox.fs.find_files(path, pattern)

        total = len(matches)
        truncated = total > max_results
        matches = matches[:max_results]

        files_with_matches = set(m.file for m in matches)

        yield self.create_json_message({
            "sandbox_id": sandbox_id,
            "path": path,
            "pattern": pattern,
            "matches": [
                {"file": m.file, "line": m.line, "content": m.content}
                for m in matches
            ],
            "count": len(matches),
            "total": total,
            "truncated": truncated,
            "files_with_matches": len(files_with_matches),
        })
        summary = f"Found {total} matches for '{pattern}' in {len(files_with_matches)} files"
        if truncated:
            summary += f" (showing first {max_results})"
        yield self.create_text_message(summary)
