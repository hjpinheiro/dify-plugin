# Proposal: Upgrade Daytona Dify Agent Tools v0.0.9

## Intent

Make the Daytona Dify plugin reliable across multi-turn agent conversations and
more ergonomic for Dify Agent strategies, by closing the highest-impact gaps
between the current implementation and the official Daytona SDK and Dify Plugin
SDK capabilities.

The v0.0.6–v0.0.8 line delivered the core tool surface (lifecycle, code/command
execution, file transfer, file read/write, discovery, Git clone, preview URL,
listing). This change targets the next release and focuses on **runtime
reliability**, **agent ergonomics**, and **release safety**, without turning the
provider into an Agent Strategy plugin.

## Motivation

- **Stopped sandboxes break reuse (critical).** Daytona sandboxes auto-stop after
  an idle interval (default 15 minutes). When an agent reuses a `sandbox_id` from
  a previous turn, the sandbox is in `STOPPED` (or `ARCHIVED`) state and
  `process.exec` / filesystem calls fail. `get_sandbox()` only calls
  `client.get(id)` and never reactivates the sandbox, so any persistent
  multi-turn workflow fails intermittently and confusingly.
- **No background execution.** Every execution tool uses synchronous
  `process.exec()` bounded by a timeout. There is no way to start a long-running
  service (HTTP server, dev server, Streamlit, etc.) and then obtain its preview
  URL, which makes `get_preview_url` largely unusable in practice.
- **Agents must manually carry `sandbox_id`.** The plugin keeps no state between
  tool calls, so the LLM must copy the sandbox ID from tool to tool. This is a
  common source of agent errors. The Dify Plugin SDK provides
  `self.session.storage`, which can persist the active sandbox per conversation.
- **No sandbox lifecycle controls.** The plugin can create/destroy/list but
  cannot start, stop, or archive a sandbox. Agents cannot pause a sandbox to
  control cost without destroying its state.
- **Chart metadata is discarded.** `run_code` extracts only `chart.png`, dropping
  the rich `artifacts.charts` metadata (type, title, axes) that helps the agent
  reason about generated visualizations.
- **Workflow reuse is limited.** Tools emit only text/json/blob messages and no
  named output variables, so the plugin is hard to chain inside Dify Workflows.
- **Release safety regression.** The v0.0.8 release shipped a corrupted
  `manifest.yaml` (broken indentation) that did not parse and could not install.
  Packaging has no automated YAML validation gate.

## Scope

This change includes:

- Automatically reactivate stopped or archived sandboxes in the shared
  `get_sandbox()` helper before returning them to a tool.
- Add background command execution backed by Daytona sessions, paired with a way
  to retrieve logs, so services can run while the agent continues.
- Add a `start_service` tool (or a `background` mode) that launches a process and
  returns control immediately, designed to pair with `get_preview_url`.
- Persist the active sandbox per conversation using `self.session.storage` and use
  it as a default when a tool is invoked without `sandbox_id`.
- Add `start_sandbox`, `stop_sandbox`, and `archive_sandbox` lifecycle tools.
- Include chart artifact metadata in `run_code` JSON output.
- Emit named output variables (`create_variable_message`) for key results such as
  `sandbox_id` and preview URLs, for Dify Workflow chaining.
- Add structured log messages for long-running operations (`create_sandbox`,
  `git_clone`, `start_service`).
- Add an automated YAML and package validation gate to the packaging step.
- Update README, manifest/provider tool lists, package metadata, and bump version
  to `0.0.9`.

## Out Of Scope

- Converting this tool provider into a Dify Agent Strategy plugin.
- Full PTY/terminal interaction tools.
- LSP / code-intelligence tools.
- Daytona MCP server integration.
- Volume management and GPU scheduling controls.
- Full Git workflow tools (push, commit, branch, pull).
- Computer-use / SSH-access tools.
- Tool consolidation/renaming that breaks existing tool names (tracked as a
  future, separately versioned change to avoid breaking installed agent configs).

## Success Criteria

- An agent can reuse a `sandbox_id` from a previous turn after the sandbox has
  auto-stopped, and execution succeeds because the sandbox is reactivated
  transparently.
- An agent can start a web service in the background and then retrieve a working
  preview URL within the same or a later turn.
- When a tool is invoked without `sandbox_id`, the plugin uses the
  conversation's active sandbox if one exists, and reports clearly when none is
  available.
- `start_sandbox`, `stop_sandbox`, and `archive_sandbox` work against the official
  SDK and return clear state metadata.
- `run_code` returns chart metadata alongside PNG blobs.
- Key tools emit named output variables usable in Dify Workflows.
- The packaging step fails fast if any YAML file does not parse, preventing a
  repeat of the v0.0.8 manifest regression.
- The package installs in Dify with the expected tool list and no
  signature/packaging regressions.

## References

- Daytona Python SDK `0.187.0` (local inspection): `Sandbox.start`, `Sandbox.stop`,
  `Sandbox.archive`, `Sandbox.wait_for_sandbox_start`, `SandboxState` enum,
  `Process.create_session`, `Process.execute_session_command`,
  `Process.get_session_command_logs`, `SessionExecuteRequest(var_async=...)`,
  `ExecuteResponse.artifacts` (stdout + charts), `Sandbox.create_signed_preview_url`.
- Dify Plugin SDK: `self.session.storage` (persistent key-value),
  `create_variable_message`, `create_log_message` / `finish_log_message`,
  `ToolLike` message helpers.
- Dify official Agent strategies plugin (`langgenius/agent`) Function Calling and
  ReAct behavior.
- Existing plugin code in `hjpinheiro/dify-plugin` v0.0.8 and the prior change
  `upgrade-daytona-agent-tools-v006`.
