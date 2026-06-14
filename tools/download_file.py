import logging
import mimetypes
import os
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _client import MAX_FILE_SIZE, build_client, daytona_operation, get_sandbox, resolve_sandbox_id

logger = logging.getLogger(__name__)

# Extensions that are safe to display inline via read_file
_TEXT_EXTENSIONS = (
    ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".md", ".csv", ".txt",
    ".xml", ".yaml", ".yml", ".html", ".css", ".sql", ".sh", ".log",
    ".toml", ".ini", ".cfg", ".conf", ".env", ".rs", ".go", ".java",
    ".c", ".cpp", ".h", ".rb", ".php", ".swift", ".kt", ".scala",
)


class DownloadFileTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        sandbox_id = resolve_sandbox_id(self, tool_parameters)

        remote_path = tool_parameters.get("remote_path")
        if not remote_path:
            raise ValueError("remote_path is required")

        daytona = build_client(self.runtime.credentials)
        sandbox = get_sandbox(daytona, sandbox_id)

        with daytona_operation("getting file info"):
            info = sandbox.fs.get_file_info(remote_path)
        if info.size and info.size > MAX_FILE_SIZE:
            raise ValueError(
                f"File size ({info.size} bytes) exceeds maximum allowed size "
                f"({MAX_FILE_SIZE} bytes)."
            )

        with daytona_operation("downloading file"):
            content = sandbox.fs.download_file(remote_path)

        if content is None:
            raise ValueError(f"Could not read '{remote_path}' from sandbox '{sandbox_id}': no content returned")

        if len(content) > MAX_FILE_SIZE:
            raise ValueError(
                f"Downloaded file size ({len(content)} bytes) exceeds maximum allowed size "
                f"({MAX_FILE_SIZE} bytes)."
            )

        filename = os.path.basename(remote_path) or "downloaded_file"
        mime_type, _ = mimetypes.guess_type(filename)
        if not mime_type:
            mime_type = "application/octet-stream"

        is_image = mime_type.startswith("image/")
        output_raw_blob = bool(tool_parameters.get("output_raw_blob", False))

        # ------------------------------------------------------------------
        # Delivery strategy
        #
        # Platform bug: dify-plugin-daemon#200
        # Non-image blobs are transformed to BINARY_LINK by Dify core's
        # message_transformer.py, but BINARY_LINK is not in the SDK's
        # MessageType enum, causing a Pydantic validation crash in agent mode.
        # Image blobs are fine (IMAGE_LINK is in the enum).
        #
        # Flow:
        #   1. Image or output_raw_blob=True  → blob (safe in all modes)
        #   2. Non-image, agent/chat mode     → upload + link fallback
        #   3. Upload fails                   → guide agent to alternatives
        # ------------------------------------------------------------------

        if is_image or output_raw_blob:
            yield from self._deliver_blob(content, mime_type, filename, sandbox_id, remote_path)
            return

        # Non-image in agent/chat mode: try Dify storage upload + link
        delivered = False
        delivery_method = "none"
        upload_file_id: str | None = None

        try:
            upload_resp = self.session.file.upload(filename, content, mime_type)
            preview_url = getattr(upload_resp, "preview_url", None)
            upload_file_id = getattr(upload_resp, "id", None)
            if preview_url:
                yield self.create_link_message(preview_url)
                delivered = True
                delivery_method = "link"
        except Exception as exc:
            logger.warning("Dify storage upload failed for %s: %s", filename, exc)

        if delivered:
            yield self.create_json_message({
                "success": True,
                "delivered": True,
                "delivery_method": delivery_method,
                "upload_file_id": upload_file_id,
                "sandbox_id": sandbox_id,
                "remote_path": remote_path,
                "size_bytes": len(content),
                "mime_type": mime_type,
                "filename": filename,
            })
            yield self.create_text_message(
                f"File '{filename}' ({len(content)} bytes, {mime_type}) has been delivered "
                f"to the user via download link. Do NOT try alternative delivery methods."
            )
        else:
            # Direct delivery failed — guide the agent to a working alternative
            is_text_like = mime_type.startswith("text/") or filename.lower().endswith(_TEXT_EXTENSIONS)

            if is_text_like:
                fallback = (
                    f"Direct delivery of '{filename}' failed (platform limitation for non-image "
                    f"files in agent mode). To show this file to the user, use the read_file tool "
                    f"to read '{remote_path}' and present the content in the chat as a formatted "
                    f"code block or text."
                )
            else:
                fallback = (
                    f"Direct delivery of '{filename}' failed (platform limitation for non-image "
                    f"files in agent mode). To deliver this binary file, use start_service to start "
                    f"an HTTP server (e.g. command='python3 -m http.server 8000' with cwd set to "
                    f"the directory containing the file), then call get_preview_url with port 8000 "
                    f"to get a public download link for the user."
                )

            yield self.create_json_message({
                "success": False,
                "delivered": False,
                "delivery_method": "none",
                "sandbox_id": sandbox_id,
                "remote_path": remote_path,
                "size_bytes": len(content),
                "mime_type": mime_type,
                "filename": filename,
                "error": "Non-image blob delivery not supported in agent mode (dify-plugin-daemon#200)",
            })
            yield self.create_text_message(fallback)

    def _deliver_blob(
        self,
        content: bytes,
        mime_type: str,
        filename: str,
        sandbox_id: str,
        remote_path: str,
    ) -> Generator[ToolInvokeMessage]:
        """Deliver file as a blob message (safe for images and workflow mode)."""
        yield self.create_blob_message(
            blob=content,
            meta={"mime_type": mime_type, "filename": filename},
        )
        yield self.create_json_message({
            "success": True,
            "delivered": True,
            "delivery_method": "blob",
            "sandbox_id": sandbox_id,
            "remote_path": remote_path,
            "size_bytes": len(content),
            "mime_type": mime_type,
            "filename": filename,
        })
        yield self.create_text_message(
            f"File '{filename}' ({len(content)} bytes, {mime_type}) has been delivered to the user. "
            f"The user can now download it. Do NOT try alternative delivery methods."
        )
