from collections.abc import Generator
from typing import Any
from urllib.parse import urlparse

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _client import build_client, daytona_operation, get_sandbox, resolve_sandbox_id


def rewrite_preview_url(url: str, proxy_domain: str) -> str:
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    parts = hostname.split(".", 1)
    if len(parts) != 2:
        return url
    subdomain = parts[0]
    path = parsed.path or "/"
    rewritten = f"https://{proxy_domain}/preview/{subdomain}{path}"
    if parsed.query:
        rewritten += f"?{parsed.query}"
    return rewritten


class GetPreviewUrlTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        sandbox_id = resolve_sandbox_id(self, tool_parameters)

        port = tool_parameters.get("port")
        if port is None or port == "":
            raise ValueError("port is required")
        port = int(port)
        if not (1 <= port <= 65535):
            raise ValueError(f"Invalid port number: {port}")

        include_token = tool_parameters.get("include_token", False)

        daytona = build_client(self.runtime.credentials)
        sandbox = get_sandbox(daytona, sandbox_id)

        with daytona_operation("getting preview URL"):
            preview = sandbox.get_preview_link(port)

        proxy_domain = (self.runtime.credentials.get("preview_proxy_domain") or "").strip()
        if proxy_domain:
            display_url = rewrite_preview_url(preview.url, proxy_domain)
        else:
            display_url = preview.url

        yield self.create_link_message(display_url)
        yield self.create_variable_message("preview_url", display_url)

        json_result: dict[str, Any] = {
            "url": display_url,
            "port": port,
            "sandbox_id": sandbox_id,
        }
        if include_token:
            json_result["token"] = preview.token
        else:
            json_result["requires_token"] = True

        yield self.create_json_message(json_result)
        yield self.create_text_message(f"Preview URL for port {port}: {display_url}")
