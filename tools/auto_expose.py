from collections.abc import Generator
from typing import Any
from urllib.parse import urlparse

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _client import build_client, daytona_operation, get_sandbox, remember_sandbox, resolve_sandbox_id


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


_SHELL_SCAN = (
    '( ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null || true ) | '
    "grep LISTEN | awk '{print $4}' | "
    "awk -F: '{print $NF+0}' | sort -un"
)


class AutoExposeTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        sandbox_id = resolve_sandbox_id(self, tool_parameters)

        daytona = build_client(self.runtime.credentials)
        sandbox = get_sandbox(daytona, sandbox_id)

        remember_sandbox(self, sandbox_id)

        ports = []

        # Try fast shell-based scan first.
        try:
            with daytona_operation("scanning ports (shell)"):
                resp = sandbox.process.exec(_SHELL_SCAN)

            if resp is not None:
                exit_code = getattr(resp, "exit_code", -1)
                result = getattr(resp, "result", "").strip()
                if getattr(resp, "artifacts", None):
                    stdout = getattr(getattr(resp, "artifacts", None), "stdout", "").strip()
                    result = stdout or result
            else:
                exit_code = -1
                result = ""

            if exit_code == 0 and result:
                ports = [
                    int(p)
                    for p in result.replace(",", "\n").splitlines()
                    if p.strip() and p.strip().isdigit()
                ]
                ports = sorted(set(ports))
        except Exception:
            pass

        # Fallback: Python socket scan (slower but always works).
        if not ports:
            try:
                scan_code = (
                    "import socket\n"
                    "ports = []\n"
                    "for port in range(1000, 10001):\n"
                    "    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
                    "    s.settimeout(0.02)\n"
                    "    try:\n"
                    "        if s.connect_ex(('127.0.0.1', port)) == 0:\n"
                    "            ports.append(str(port))\n"
                    "    finally:\n"
                    "        s.close()\n"
                    "print(','.join(ports))\n"
                )
                with daytona_operation("scanning ports (python)"):
                    code_resp = sandbox.process.code_run(scan_code, timeout=60)

                code_result = getattr(code_resp, "result", "") or ""
                ports = [
                    int(p.strip())
                    for p in code_result.split(",")
                    if p.strip() and p.strip().isdigit()
                ]
                ports = sorted(set(ports))
            except Exception:
                pass

        proxy_domain = (self.runtime.credentials.get("preview_proxy_domain") or "").strip()

        url_results = []
        for port in ports:
            try:
                with daytona_operation(f"getting preview link for port {port}"):
                    preview = sandbox.get_preview_link(port)
                raw_url = preview.url
                if proxy_domain:
                    raw_url = rewrite_preview_url(raw_url, proxy_domain)

                yield self.create_link_message(raw_url)
                url_results.append({"port": port, "url": raw_url})
            except Exception:
                url_results.append({"port": port, "url": None, "error": "Failed to get preview link"})

        yield self.create_json_message({"ports": url_results, "sandbox_id": sandbox_id})
        yield self.create_variable_message("ports", url_results)

        if ports:
            yield self.create_text_message(
                f"Found {len(ports)} listening port(s): {', '.join(str(p) for p in ports)}. "
                f"Preview URLs generated above."
            )
        else:
            yield self.create_text_message(
                "No listening ports detected in the sandbox (scanned range 1000-10000). "
                "Make sure a service is running and try again."
            )
