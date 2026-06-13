# Design: Upgrade Daytona Dify Agent Tools v0.0.6

## Overview

The plugin remains a Dify tool provider. It should not become an Agent Strategy plugin. Dify's official `langgenius/agent` plugin already provides Function Calling and ReAct strategies that can invoke this provider's tools.

The design goal is to expose a compact, agent-friendly subset of the Daytona SDK rather than mirroring the entire SDK surface. Tools should be easy for LLMs to select, return bounded observations, and avoid leaking secrets or producing unnecessarily large outputs.

## Daytona SDK Compatibility

Use the official SDK API shape observed in Daytona `0.187.0`:

- `Daytona.list(query: ListSandboxesQuery | None = None)`
- `ListSandboxesQuery(limit=...)`
- `Daytona.create(params, timeout=...)`
- `Sandbox.fs.*` for filesystem operations
- `Sandbox.git.*` for Git operations
- `Sandbox.process.exec(...)` and `Sandbox.process.code_run(...)`

The provider validation should instantiate `ListSandboxesQuery(limit=1)` and then consume at most one item from `daytona.list(query)`.

## Dependency Strategy

Pin Daytona to the validated SDK family to prevent silent behavior changes:

- Preferred: `daytona>=0.187.0,<0.188.0`

Keep the Dify plugin SDK range aligned with what the plugin package can actually run with. If the plugin package is intentionally compatible with `dify_plugin>=0.3.0,<0.6.0`, the local venv/lockfile should not drift to an incompatible major/minor without deliberate testing. If runtime testing uses `dify_plugin==0.9.0`, update the package constraints explicitly and validate against the deployed Dify plugin daemon.

## Agent-Friendly Tool Set

The provider should prioritize this core workflow:

1. Create or reuse a sandbox.
2. Clone or upload project files.
3. Discover files.
4. Read specific files.
5. Write or update files.
6. Run commands/tests/code.
7. Download artifacts or expose preview URLs.
8. Stop/delete the sandbox.

Add only the missing minimum primitives now:

- `read_file`
- `write_file`

Defer broad SDK wrappers until there is a concrete use case.

## `read_file`

Use `sandbox.fs.get_file_info(remote_path)` before reading when possible. Reject files over a configured byte limit. Decode text as UTF-8 by default with replacement for invalid bytes. Return:

- JSON: `sandbox_id`, `remote_path`, `content`, `size_bytes`, `encoding`, `truncated`
- Text: the readable content or a concise summary

Support an optional `max_bytes` parameter clamped to a safe upper bound. If truncation occurs, include `truncated: true` and avoid pretending the content is complete.

## `write_file`

Use `sandbox.fs.upload_file(content_bytes, remote_path)`. Accept text content from the LLM and encode as UTF-8 by default. Enforce `MAX_FILE_SIZE`. Return JSON and text confirmation with size. Do not provide append semantics in the first version unless needed; agents can read and rewrite complete files.

## Bounded Outputs

All tools that can return lists or match sets should support bounded output:

- `list_files`: `max_results`, `truncated`
- `search_files`: `max_results`, `truncated`
- `find_in_files`: clamp existing `max_results` to a safe range and include `total` when known

Recommended clamp:

- default: 50
- minimum: 1
- maximum: 200

Text observations should summarize counts and truncation. JSON should contain the structured subset and metadata.

## Git Clone Verification

After `sandbox.git.clone(...)`, call `sandbox.git.status(path)` when possible. Return `current_branch`, `file_status_count`, `ahead`, `behind`, and `branch_published` when available.

Fallback to `sandbox.fs.list_files(path)` if Git status fails, because the clone may still have succeeded while status is unavailable.

Never return username, password, or token values.

## Secret Handling

`git_clone.password` should be a secret runtime/form parameter, not an LLM-generated parameter. This avoids asking the model to invent or echo credentials.

The tool implementation should continue to pass credentials directly to the Daytona SDK rather than embedding them in shell commands.

## Preview URL Token Handling

`get_preview_url` currently returns the preview token in JSON. Because Dify Agent strategies include JSON tool responses in LLM observations, this can expose the token to the LLM context.

For this change, prefer one of these approaches:

- Omit `token` from the default JSON output and keep only `url`, `port`, and `sandbox_id`.
- Return a boolean `requires_token` and a masked token preview if needed.
- Add an explicit parameter such as `include_token` defaulting to false.

The safest default is to omit the token unless the user explicitly asks for it.

## Ephemeral Sandbox Semantics

When `run_code` or `run_command` creates a sandbox implicitly, create it with explicit ephemeral settings where supported:

- `CreateSandboxFromSnapshotParams(language=..., ephemeral=True, auto_stop_interval=5)` for code execution
- `CreateSandboxFromSnapshotParams(ephemeral=True, auto_stop_interval=5)` for command execution

Continue deleting the sandbox in `finally` after execution.

## Sandbox Creation Controls

Expose only high-value official SDK controls in `create_sandbox`:

- `public`
- `labels` as JSON object string
- `network_block_all`
- `network_allow_list`
- `auto_delete_interval`
- `auto_archive_interval`
- `ephemeral`

Do not expose GPU, volumes, PTY, LSP, or linked sandboxes in this change.

## Package and Manifest Updates

Any new tool requires updates to:

- `provider/daytona.yaml`
- new tool YAML files under `tools/`
- new tool Python files under `tools/`
- `manifest.yaml` version
- `README.md` tool reference
- package validation artifact (`daytona.difypkg`) if release packaging is performed

The existing `package.py` behavior of writing files only and avoiding directory entries should be preserved.

## Testing Strategy

Minimum verification:

- Static import check for all tool modules.
- Package generation with `package.py`.
- Inspect package zip to confirm no directory entries and all new tool files are included.
- Provider credential validation path mocked or smoke-tested against valid Daytona credentials if available.
- Manual Dify plugin installation test after packaging.
- Agent workflow smoke test: create sandbox, clone repo, list files, read file, write file, run command, destroy sandbox.

## Risks

- Tight dependency pinning can require future updates when Daytona SDK advances.
- Dify plugin SDK version compatibility must be validated against the deployed Dify plugin daemon, not only the local venv.
- Returning file content as text can increase token usage; truncation must be enforced.
- Preview token handling can break workflows that relied on the raw token being present in JSON; use an opt-in parameter if needed.
