from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from daytona import ListSandboxesQuery

from _client import build_client, daytona_operation


class ListSandboxesTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        limit = tool_parameters.get("limit", 20)
        limit = int(limit) if limit else 20
        if limit < 1:
            limit = 1
        if limit > 100:
            limit = 100

        state = tool_parameters.get("state") or None

        daytona = build_client(self.runtime.credentials)

        query_kwargs: dict[str, Any] = {"limit": limit}
        if state:
            query_kwargs["states"] = [state]

        query = ListSandboxesQuery(**query_kwargs)

        with daytona_operation("listing sandboxes"):
            sandboxes = list(daytona.list(query))

        entries = []
        state_counts: dict[str, int] = {}
        for sb in sandboxes:
            sb_state = getattr(sb.state, "value", sb.state) if sb.state else "unknown"
            state_counts[sb_state] = state_counts.get(sb_state, 0) + 1
            entries.append({
                "id": sb.id,
                "name": sb.name,
                "state": sb_state,
                "cpu": sb.cpu,
                "memory": sb.memory,
                "created_at": sb.created_at,
            })

        yield self.create_json_message({
            "sandboxes": entries,
            "count": len(entries),
            "by_state": state_counts,
        })
        state_summary = ", ".join(f"{v} {k}" for k, v in sorted(state_counts.items()))
        yield self.create_text_message(
            f"Found {len(entries)} sandboxes ({state_summary})"
        )
