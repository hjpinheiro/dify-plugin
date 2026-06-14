import base64
import json
import os
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from daytona import CodeRunParams, CreateSandboxFromSnapshotParams

from _client import (
    EXECUTION_TIMEOUT,
    MAX_FILE_SIZE,
    build_client,
    daytona_operation,
    get_sandbox,
    inject_text_files,
    remember_sandbox,
    resolve_timeout,
    try_resolve_sandbox_id,
    validate_language,
)


class RunCodeTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        daytona = build_client(self.runtime.credentials)

        sandbox_id = try_resolve_sandbox_id(self, tool_parameters)
        ephemeral = not sandbox_id

        language = validate_language(tool_parameters.get("language", "python"))
        stateful = tool_parameters.get("stateful", True)
        timeout = resolve_timeout(tool_parameters.get("timeout")) or EXECUTION_TIMEOUT

        use_code_interpreter = stateful and language == "python"

        if sandbox_id:
            sandbox = get_sandbox(daytona, sandbox_id)
            remember_sandbox(self, sandbox.id)
        else:
            ephemeral_language = "python" if use_code_interpreter else language
            with daytona_operation("creating ephemeral sandbox"):
                sandbox = daytona.create(CreateSandboxFromSnapshotParams(
                    language=ephemeral_language,
                    ephemeral=True,
                    auto_stop_interval=5,
                ))

        uploaded_paths = self._inject_files(sandbox, tool_parameters)

        text_files_json = tool_parameters.get("input_text_files") or ""
        if text_files_json:
            text_paths = inject_text_files(sandbox, text_files_json)
            uploaded_paths = uploaded_paths + text_paths

        env_vars = self._parse_env_vars(tool_parameters.get("env_vars"))

        try:
            if use_code_interpreter:
                yield from self._execute_stateful(sandbox, tool_parameters["code"], uploaded_paths, env_vars, timeout)
            else:
                yield from self._execute_standalone(sandbox, tool_parameters["code"], uploaded_paths, env_vars, timeout)
        finally:
            if ephemeral:
                try:
                    sandbox.delete()
                except Exception:
                    pass

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

    def _inject_files(self, sandbox, tool_parameters: dict[str, Any]) -> list[str]:
        """Upload input_files to the sandbox workspace. Returns list of uploaded paths."""
        files = tool_parameters.get("input_files")
        if not files:
            return []
        if not isinstance(files, list):
            files = [files]

        uploaded = []
        for f in files:
            if not hasattr(f, "blob") or not hasattr(f, "filename"):
                continue
            blob = f.blob
            if len(blob) > MAX_FILE_SIZE:
                raise ValueError(
                    f"File '{f.filename}' size ({len(blob)} bytes) exceeds maximum "
                    f"allowed size ({MAX_FILE_SIZE} bytes)."
                )
            safe_filename = os.path.basename(f.filename) if f.filename else "upload"
            remote_path = f"/home/daytona/workspace/{safe_filename}"
            with daytona_operation(f"uploading {f.filename}"):
                sandbox.fs.upload_file(blob, remote_path)
            uploaded.append(remote_path)
        return uploaded

    def _execute_stateful(
        self, sandbox, code: str, uploaded_paths: list[str], env_vars: dict[str, str] | None, timeout: int = EXECUTION_TIMEOUT,
    ) -> Generator[ToolInvokeMessage]:
        with daytona_operation("executing code (stateful)"):
            result = sandbox.code_interpreter.run_code(
                code, envs=env_vars, timeout=timeout
            )

        error = getattr(result, "error", None)

        if error is not None:
            error_name = getattr(error, "name", "UnknownError")
            error_value = getattr(error, "value", "")
            error_traceback = getattr(error, "traceback", "")
            text = f"{error_name}: {error_value}"
            yield self.create_text_message(text)
            yield self.create_json_message({
                "exit_code": 1,
                "error_name": error_name,
                "error_value": error_value,
                "error_traceback": error_traceback,
                "sandbox_id": sandbox.id,
                "uploaded_files": uploaded_paths,
            })
            yield self.create_variable_message("sandbox_id", sandbox.id)
            yield self.create_variable_message("exit_code", 1)
        else:
            output_parts = []
            stdout = getattr(result, "stdout", "") or ""
            stderr = getattr(result, "stderr", "") or ""
            if stdout:
                output_parts.append(stdout)
            if stderr:
                output_parts.append(stderr)
            output = "\n".join(output_parts) if output_parts else "(no output)"
            yield self.create_text_message(output)
            yield self.create_json_message({
                "exit_code": 0,
                "output": output,
                "sandbox_id": sandbox.id,
                "uploaded_files": uploaded_paths,
            })
            yield self.create_variable_message("sandbox_id", sandbox.id)
            yield self.create_variable_message("exit_code", 0)

    def _execute_standalone(
        self, sandbox, code: str, uploaded_paths: list[str], env_vars: dict[str, str] | None, timeout: int = EXECUTION_TIMEOUT,
    ) -> Generator[ToolInvokeMessage]:
        with daytona_operation("executing code"):
            params = CodeRunParams(env=env_vars) if env_vars else None
            response = sandbox.process.code_run(
                code, params=params, timeout=timeout
            )

        artifacts = getattr(response, "artifacts", None)
        charts = getattr(artifacts, "charts", None) if artifacts else None

        if charts:
            for chart in charts:
                if getattr(chart, "png", None):
                    png_bytes = base64.b64decode(chart.png)
                    yield self.create_blob_message(blob=png_bytes, meta={"mime_type": "image/png"})

        charts_meta = []
        if charts:
            for chart in charts:
                type_val = getattr(chart, "type", None)
                type_str = getattr(type_val, "value", type_val) if type_val else None
                charts_meta.append({
                    "type": type_str,
                    "title": getattr(chart, "title", None),
                })

        yield self.create_text_message(response.result or "(no output)")

        yield self.create_json_message({
            "exit_code": response.exit_code,
            "output": response.result,
            "sandbox_id": sandbox.id,
            "charts_count": len(charts) if charts else 0,
            "charts": charts_meta,
            "uploaded_files": uploaded_paths,
        })

        yield self.create_variable_message("sandbox_id", sandbox.id)
        yield self.create_variable_message("exit_code", response.exit_code)