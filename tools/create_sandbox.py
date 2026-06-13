import json
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from daytona import (
    CreateSandboxFromImageParams,
    CreateSandboxFromSnapshotParams,
    Resources,
)

from _client import build_client, daytona_operation, validate_language


class CreateSandboxTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        daytona = build_client(self.runtime.credentials)

        name = tool_parameters.get("name") or None
        snapshot = tool_parameters.get("snapshot") or None
        image = tool_parameters.get("image") or None

        language = validate_language(tool_parameters.get("language", "python"))

        env_vars = self._parse_env_vars(tool_parameters.get("env_vars"))

        auto_stop = tool_parameters.get("auto_stop_interval", 15)
        if isinstance(auto_stop, float):
            auto_stop = int(auto_stop)

        public = tool_parameters.get("public")
        if public is not None:
            public = bool(public)

        ephemeral = tool_parameters.get("ephemeral")
        if ephemeral is not None:
            ephemeral = bool(ephemeral)

        network_block_all = tool_parameters.get("network_block_all")
        if network_block_all is not None:
            network_block_all = bool(network_block_all)

        network_allow_list = tool_parameters.get("network_allow_list") or None

        auto_delete_interval = tool_parameters.get("auto_delete_interval")
        if auto_delete_interval is not None:
            auto_delete_interval = int(auto_delete_interval)

        auto_archive_interval = tool_parameters.get("auto_archive_interval")
        if auto_archive_interval is not None:
            auto_archive_interval = int(auto_archive_interval)

        labels = self._parse_labels(tool_parameters.get("labels"))

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

        with daytona_operation("creating sandbox"):
            sandbox = daytona.create(params, timeout=180)

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
        if cpu is None and memory is None and disk is None:
            return None
        kwargs: dict[str, int] = {}
        if cpu is not None:
            kwargs["cpu"] = int(cpu)
        if memory is not None:
            kwargs["memory"] = int(memory)
        if disk is not None:
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
