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

        raw_expiry = tool_parameters.get("expires_in_seconds")
        resolved_expiry = None
        if raw_expiry is not None and raw_expiry != "":
            try:
                resolved_expiry = max(60, min(int(raw_expiry), 86400))
            except (ValueError, TypeError):
                pass

        daytona = build_client(self.runtime.credentials)
        sandbox = get_sandbox(daytona, sandbox_id)

        preview_url = None
        preview_token = None

        with daytona_operation("getting preview URL"):
            probe = sandbox.get_preview_link(port)
            probe_token = getattr(probe, "token", None)

            if probe_token:
                signed = sandbox.create_signed_preview_url(
                    port, expires_in_seconds=resolved_expiry
                )
                preview_url = signed.url
                preview_token = signed.token
            else:
                preview_url = probe.url

        proxy_domain = (self.runtime.credentials.get("preview_proxy_domain") or "").strip()

        if proxy_domain:
            display_url = rewrite_preview_url(preview_url, proxy_domain)
        else:
            display_url = preview_url

        yield self.create_link_message(display_url)
        yield self.create_variable_message("preview_url", display_url)

        json_result: dict[str, Any] = {
            "url": display_url,
            "port": port,
            "sandbox_id": sandbox_id,
        }

        if include_token:
            json_result["token"] = preview_token

        yield self.create_json_message(json_result)

        text_parts = [f"Preview URL for port {port}: {display_url}"]
        yield self.create_text_message(" ".join(text_parts))
