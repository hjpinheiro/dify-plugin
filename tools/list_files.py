from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _client import build_client, daytona_operation, get_sandbox


class ListFilesTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        sandbox_id = tool_parameters.get("sandbox_id")
        if not sandbox_id:
            raise ValueError("sandbox_id is required")

        path = tool_parameters.get("path")
        if not path:
            raise ValueError("path is required")

        daytona = build_client(self.runtime.credentials)
        sandbox = get_sandbox(daytona, sandbox_id)

        with daytona_operation("listing files"):
            files = sandbox.fs.list_files(path)

        entries = []
        total_size = 0
        dir_count = 0
        file_count = 0
        for f in files:
            size = f.size or 0
            total_size += size if not f.is_dir else 0
            if f.is_dir:
                dir_count += 1
            else:
                file_count += 1
            entries.append({
                "name": f.name,
                "is_dir": f.is_dir,
                "size": size,
                "mod_time": f.mod_time,
                "permissions": f.permissions,
                "owner": f.owner,
                "group": f.group,
            })

        yield self.create_json_message({
            "sandbox_id": sandbox_id,
            "path": path,
            "files": entries,
            "count": len(entries),
            "dirs": dir_count,
            "files_count": file_count,
        })
        yield self.create_text_message(
            f"Found {len(entries)} items in {path}: "
            f"{dir_count} dirs, {file_count} files ({total_size} bytes)"
        )
