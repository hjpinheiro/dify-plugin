import base64
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from daytona import CreateSandboxFromSnapshotParams

from _client import EXECUTION_TIMEOUT, build_client, daytona_operation, get_sandbox, validate_language


class RunCodeTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        daytona = build_client(self.runtime.credentials)

        sandbox_id = tool_parameters.get("sandbox_id", "")
        ephemeral = not sandbox_id

        language = validate_language(tool_parameters.get("language", "python"))

        if sandbox_id:
            sandbox = get_sandbox(daytona, sandbox_id)
        else:
            with daytona_operation("creating ephemeral sandbox"):
                sandbox = daytona.create(CreateSandboxFromSnapshotParams(language=language))

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

            yield self.create_text_message(response.result or "(no output)")

            yield self.create_json_message({
                "exit_code": response.exit_code,
                "output": response.result,
                "sandbox_id": sandbox.id,
                "charts_count": len(charts) if charts else 0,
            })
        finally:
            if ephemeral:
                try:
                    sandbox.delete()
                except Exception:
                    pass