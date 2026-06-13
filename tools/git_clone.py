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

        current_branch = None
        file_count = 0

        try:
            with daytona_operation("verifying clone via git status"):
                status = sandbox.git.status(path)
                current_branch = status.current_branch
        except Exception:
            try:
                with daytona_operation("verifying clone via file listing"):
                    files = sandbox.fs.list_files(path)
                    file_count = len(files)
            except Exception:
                pass

        result: dict[str, Any] = {
            "sandbox_id": sandbox_id,
            "url": url,
            "path": path,
            "branch": current_branch or branch or "default",
            "commit_id": commit_id,
            "status": "cloned",
        }
        if current_branch:
            result["current_branch"] = current_branch
        if file_count:
            result["files_in_root"] = file_count

        yield self.create_json_message(result)

        parts = [f"Cloned {url}"]
        if current_branch:
            parts.append(f"(branch: {current_branch})")
        elif branch:
            parts.append(f"(branch: {branch})")
        elif commit_id:
            parts.append(f"(commit: {commit_id})")
        parts.append(f"into {path}")
        if file_count:
            parts.append(f"({file_count} items)")
        yield self.create_text_message(" ".join(parts))
