import json
import time
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from daytona import SessionExecuteRequest

from _client import (
    build_client,
    compose_shell_command,
    daytona_operation,
    get_sandbox,
    remember_sandbox,
    resolve_sandbox_id,
)
from tools.get_preview_url import rewrite_preview_url


class StartServiceTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        sandbox_id = resolve_sandbox_id(self, tool_parameters)
        command = tool_parameters.get("command")
        if not command:
            raise ValueError("command is required")

        port = tool_parameters.get("port")
        cwd = tool_parameters.get("cwd") or None
        env_vars = self._parse_env_vars(tool_parameters.get("env_vars"))

        session_id = tool_parameters.get("session_id") or f"svc-{int(time.time())}"

        daytona = build_client(self.runtime.credentials)
        sandbox = get_sandbox(daytona, sandbox_id)

        try:
            with daytona_operation("creating session"):
                sandbox.process.create_session(session_id)
        except Exception:
            pass

        wrapped_command = compose_shell_command(command, cwd=cwd, env_vars=env_vars)

        with daytona_operation("starting background service"):
            req = SessionExecuteRequest(command=wrapped_command, run_async=True)
            response = sandbox.process.execute_session_command(session_id, req)

        cmd_id = getattr(response, "cmd_id", None)

        startup_logs = ""
        try:
            time.sleep(2)  # Give the service a moment to start and emit output
            with daytona_operation("reading startup logs"):
                logs = sandbox.process.get_session_command_logs(session_id, cmd_id)
                if logs:
                    stdout = getattr(logs, "stdout", "") or ""
                    stderr = getattr(logs, "stderr", "") or ""
                    startup_logs = (stdout + stderr)[:2000]
            # Check if service exited immediately (crash detection)
            try:
                cmd_status = sandbox.process.get_session_command(session_id, cmd_id)
                if getattr(cmd_status, "exit_code", None) is not None:
                    startup_logs = "[service exited immediately] " + startup_logs
            except Exception:
                pass
        except Exception:
            pass

        remember_sandbox(self, sandbox_id)

        json_result: dict[str, Any] = {
            "sandbox_id": sandbox_id,
            "session_id": session_id,
            "cmd_id": cmd_id,
            "command": command,
            "status": "running",
        }
        if port:
            json_result["port"] = int(port)
            preview_url = self._get_preview_url(sandbox, port)
            if preview_url:
                json_result["preview_url"] = preview_url
        if startup_logs:
            json_result["startup_logs"] = startup_logs

        yield self.create_json_message(json_result)
        text_parts = [f"Background service started in session '{session_id}'."]
        if port:
            text_parts.append(f"It should be available on port {port} — use get_preview_url to get the public URL.")
        if startup_logs:
            text_parts.append(f"Startup logs:\n{startup_logs[:500]}")
        yield self.create_text_message(" ".join(text_parts))

    @staticmethod
    def _parse_env_vars(raw: Any) -> dict[str, str] | None:
        if not raw:
            return None
        if isinstance(raw, dict):
            return {str(k): str(v) for k, v in raw.items()}
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError) as e:
            raise ValueError(f"env_vars must be a JSON object string: {e}")
        if not isinstance(parsed, dict):
            raise ValueError("env_vars must be a JSON object")
        return {str(k): str(v) for k, v in parsed.items()}

    def _get_preview_url(self, sandbox: Any, port: Any) -> str | None:
        try:
            with daytona_operation("getting preview URL"):
                probe = sandbox.get_preview_link(int(port))
                probe_token = getattr(probe, "token", None)
                if probe_token:
                    signed = sandbox.create_signed_preview_url(int(port), expires_in_seconds=3600)
                    url = signed.url
                else:
                    url = probe.url
        except Exception:
            return None

        proxy_domain = (self.runtime.credentials.get("preview_proxy_domain") or "").strip()
        if proxy_domain:
            url = rewrite_preview_url(url, proxy_domain)
        return url
