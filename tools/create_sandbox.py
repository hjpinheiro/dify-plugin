import json
import logging
from collections.abc import Generator
from typing import Any

logger = logging.getLogger(__name__)

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from daytona import (
    CreateSandboxFromImageParams,
    CreateSandboxFromSnapshotParams,
    Resources,
)

from _client import (
    _CONVERSATION_LABEL_KEY,
    build_client,
    daytona_operation,
    find_any_sandbox,
    find_sandbox_by_conversation,
    forget_sandbox,
    get_conversation_id,
    get_sandbox,
    label_sandbox,
    recall_sandbox,
    remember_sandbox,
    validate_language,
)


class CreateSandboxTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        daytona = build_client(self.runtime.credentials)

        force_new = bool(tool_parameters.get("force_new", False))

        conv_id = get_conversation_id(self)

        if not force_new:
            # PRIMARY: label-based discovery via conversation_id (cross-invocation)
            existing_id = None
            found_via = None
            if conv_id:
                existing_id = find_sandbox_by_conversation(daytona, conv_id)
                if existing_id:
                    found_via = "conversation_label"

            # SECONDARY: session storage (same-invocation only)
            if not existing_id:
                existing_id = recall_sandbox(self)
                if existing_id:
                    found_via = "session_storage"

            # FALLBACK: most recent sandbox (always tried as last resort)
            if not existing_id:
                existing_id = find_any_sandbox(daytona)
                if existing_id:
                    found_via = "any_sandbox"

            if existing_id:
                try:
                    sandbox_obj = get_sandbox(daytona, existing_id, auto_start=True, wait=True)

                    # DYNAMIC PROMOTION: if claimed from unlabeled pool, label it
                    # to this conversation so future lookups find it instantly
                    if found_via == "any_sandbox" and conv_id:
                        if label_sandbox(daytona, existing_id, conv_id):
                            found_via = "any_sandbox→labeled"

                    remember_sandbox(self, existing_id)
                    yield self.create_variable_message("sandbox_id", existing_id)
                    yield self.create_json_message({
                        "sandbox_id": existing_id,
                        "reused": True,
                        "conversation_id": conv_id,
                        "found_via": found_via,
                        "message": f"Reusing existing sandbox: {existing_id}",
                    })
                    yield self.create_text_message(
                        f"Reusing existing sandbox for this conversation: {existing_id}"
                    )
                    return
                except Exception as e:
                    logger.warning("Sandbox '%s' found but failed to activate — creating new one: %s", existing_id, e, exc_info=True)
                    forget_sandbox(self)

        def _clean_str(key: str) -> str | None:
            v = tool_parameters.get(key)
            return v if v else None

        def _clean_int(key: str) -> int | None:
            v = tool_parameters.get(key)
            if v is None or v == "":
                return None
            return int(v)

        def _clean_bool(key: str) -> bool | None:
            v = tool_parameters.get(key)
            if v is None or v == "":
                return None
            if isinstance(v, str):
                return v.lower() in ("true", "1", "yes")
            return bool(v)

        name = _clean_str("name")
        snapshot = _clean_str("snapshot")
        image = _clean_str("image")

        language = validate_language(tool_parameters.get("language") or "python")

        env_vars = self._parse_env_vars(tool_parameters.get("env_vars"))

        auto_stop = tool_parameters.get("auto_stop_interval")
        if auto_stop is None or auto_stop == "":
            auto_stop = 15
        if isinstance(auto_stop, float):
            auto_stop = int(auto_stop)

        public = _clean_bool("public")
        ephemeral = _clean_bool("ephemeral")
        network_block_all = _clean_bool("network_block_all")
        network_allow_list = _clean_str("network_allow_list")

        auto_delete_interval = _clean_int("auto_delete_interval")
        auto_archive_interval = _clean_int("auto_archive_interval")

        labels = self._parse_labels(tool_parameters.get("labels"))

        if conv_id:
            labels = labels or {}
            labels[_CONVERSATION_LABEL_KEY] = conv_id

        common_kwargs: dict[str, Any] = {
            "language": language,
            "auto_stop_interval": auto_stop,
        }
        if name:
            common_kwargs["name"] = name
        if env_vars:
            common_kwargs["env_vars"] = env_vars
        if public is not None:
            common_kwargs["public"] = public
        if ephemeral is not None:
            common_kwargs["ephemeral"] = ephemeral
        if network_block_all is not None:
            common_kwargs["network_block_all"] = network_block_all
        if network_allow_list:
            common_kwargs["network_allow_list"] = network_allow_list
        if auto_delete_interval is not None:
            common_kwargs["auto_delete_interval"] = auto_delete_interval
        if auto_archive_interval is not None:
            common_kwargs["auto_archive_interval"] = auto_archive_interval
        if labels:
            common_kwargs["labels"] = labels

        if snapshot:
            params = CreateSandboxFromSnapshotParams(snapshot=snapshot, **common_kwargs)
        elif image:
            resources = self._build_resources(tool_parameters)
            image_kwargs = dict(common_kwargs)
            image_kwargs["image"] = image
            if resources:
                image_kwargs["resources"] = resources
            params = CreateSandboxFromImageParams(**image_kwargs)
        else:
            params = CreateSandboxFromSnapshotParams(**common_kwargs)

        log = self.create_log_message(
            label="Creating Sandbox",
            data={"language": language, "snapshot": snapshot or "default"},
            status=ToolInvokeMessage.LogMessage.LogStatus.START,
        )
        yield log

        with daytona_operation("creating sandbox"):
            sandbox = daytona.create(params, timeout=180)

        yield self.finish_log_message(log, data={"sandbox_id": sandbox.id})

        remember_sandbox(self, sandbox.id)

        yield self.create_variable_message("sandbox_id", sandbox.id)

        yield self.create_json_message({
            "sandbox_id": sandbox.id,
        })
        yield self.create_text_message(f"Sandbox created: {sandbox.id}")

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

    @staticmethod
    def _build_resources(tool_parameters: dict[str, Any]) -> Resources | None:
        cpu = tool_parameters.get("cpu")
        memory = tool_parameters.get("memory")
        disk = tool_parameters.get("disk")
        if cpu in (None, "") and memory in (None, "") and disk in (None, ""):
            return None
        kwargs: dict[str, int] = {}
        if cpu not in (None, ""):
            kwargs["cpu"] = int(cpu)
        if memory not in (None, ""):
            kwargs["memory"] = int(memory)
        if disk not in (None, ""):
            kwargs["disk"] = int(disk)
        return Resources(**kwargs)

    @staticmethod
    def _parse_labels(raw: Any) -> dict[str, str] | None:
        if not raw:
            return None
        if isinstance(raw, dict):
            return {str(k): str(v) for k, v in raw.items()}
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError) as e:
            raise ValueError(f"labels must be a JSON object string: {e}")
        if not isinstance(parsed, dict):
            raise ValueError("labels must be a JSON object")
        return {str(k): str(v) for k, v in parsed.items()}
