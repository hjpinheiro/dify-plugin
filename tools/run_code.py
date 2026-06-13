import base64
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from daytona import CreateSandboxFromSnapshotParams

from _client import EXECUTION_TIMEOUT, MAX_FILE_SIZE, build_client, daytona_operation, get_sandbox, remember_sandbox, try_resolve_sandbox_id, validate_language


class RunCodeTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        daytona = build_client(self.runtime.credentials)

        sandbox_id = try_resolve_sandbox_id(self, tool_parameters)
        ephemeral = not sandbox_id

        language = validate_language(tool_parameters.get("language", "python"))
        stateful = tool_parameters.get("stateful", True)

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

        try:
            if use_code_interpreter:
                yield from self._execute_stateful(sandbox, tool_parameters["code"], uploaded_paths)
            else:
                yield from self._execute_standalone(sandbox, tool_parameters["code"], uploaded_paths)
        finally:
            if ephemeral:
                try:
                    sandbox.delete()
                except Exception:
                    pass

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
            remote_path = f"/home/daytona/workspace/{f.filename}"
            with daytona_operation(f"uploading {f.filename}"):
                sandbox.fs.upload_file(blob, remote_path)
            uploaded.append(remote_path)
        return uploaded

    def _execute_stateful(
        self, sandbox, code: str, uploaded_paths: list[str],
    ) -> Generator[ToolInvokeMessage]:
        with daytona_operation("executing code (stateful)"):
            result = sandbox.code_interpreter.run_code(
                code, timeout=EXECUTION_TIMEOUT
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
        self, sandbox, code: str, uploaded_paths: list[str],
    ) -> Generator[ToolInvokeMessage]:
        with daytona_operation("executing code"):
            response = sandbox.process.code_run(
                code, timeout=EXECUTION_TIMEOUT
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