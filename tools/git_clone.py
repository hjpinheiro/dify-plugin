from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _client import build_client, daytona_operation, get_sandbox


class GitCloneTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        sandbox_id = tool_parameters.get("sandbox_id")
        if not sandbox_id:
            raise ValueError("sandbox_id is required")

        url = tool_parameters.get("url")
        if not url:
            raise ValueError("url is required")

        path = tool_parameters.get("path")
        if not path:
            raise ValueError("path is required")

        branch = tool_parameters.get("branch") or None
        commit_id = tool_parameters.get("commit_id") or None
        username = tool_parameters.get("username") or None
        password = tool_parameters.get("password") or None

        daytona = build_client(self.runtime.credentials)
        sandbox = get_sandbox(daytona, sandbox_id)

        with daytona_operation("cloning git repository"):
            sandbox.git.clone(
                url=url,
                path=path,
                branch=branch,
                commit_id=commit_id,
                username=username,
                password=password,
                insecure_skip_tls=False,
            )

        # Verify clone by listing the target directory
        file_count = 0
        try:
            with daytona_operation("verifying clone"):
                files = sandbox.fs.list_files(path)
                file_count = len(files)
        except Exception:
            pass  # Non-fatal: clone succeeded even if listing fails

        yield self.create_json_message({
            "sandbox_id": sandbox_id,
            "url": url,
            "path": path,
            "branch": branch or "default",
            "commit_id": commit_id,
            "status": "cloned",
            "files_in_root": file_count,
        })
        parts = [f"Cloned {url}"]
        if branch:
            parts.append(f"(branch: {branch})")
        elif commit_id:
            parts.append(f"(commit: {commit_id})")
        parts.append(f"into {path}")
        if file_count:
            parts.append(f"({file_count} items)")
        yield self.create_text_message(" ".join(parts))
