import base64
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from daytona import CreateSandboxFromSnapshotParams

from _client import EXECUTION_TIMEOUT, build_client, daytona_operation, get_sandbox, remember_sandbox, recall_sandbox, validate_language


class RunCodeTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        daytona = build_client(self.runtime.credentials)

        explicit_id = tool_parameters.get("sandbox_id") or ""
        stored_id = recall_sandbox(self) if not explicit_id else ""
        sandbox_id = explicit_id or stored_id
        ephemeral = not sandbox_id

        language = validate_language(tool_parameters.get("language", "python"))

        if sandbox_id:
            sandbox = get_sandbox(daytona, sandbox_id)
            remember_sandbox(self, sandbox.id)
        else:
            with daytona_operation("creating ephemeral sandbox"):
                sandbox = daytona.create(CreateSandboxFromSnapshotParams(
                    language=language,
                    ephemeral=True,
                    auto_stop_interval=5,
                ))

        try:
            with daytona_operation("executing code"):
                response = sandbox.process.code_run(
                    tool_parameters["code"], timeout=EXECUTION_TIMEOUT
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
            })

            yield self.create_variable_message("sandbox_id", sandbox.id)
            yield self.create_variable_message("exit_code", response.exit_code)
        finally:
            if ephemeral:
                try:
                    sandbox.delete()
                except Exception:
                    pass