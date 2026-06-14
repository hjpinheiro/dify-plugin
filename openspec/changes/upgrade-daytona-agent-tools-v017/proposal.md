## Why

The Daytona Dify plugin already exposes strong capabilities, but it still works
poorly with the official Dify Agent strategies in common multi-step tasks. The
main gap is not Daytona itself; it is the mismatch between the plugin's runtime
contracts, the Daytona SDK execution model, and Dify Agent constraints such as
stripped `file`/`files` schemas and weak handling of non-text tool messages.

## What Changes

- Refactor `run_command` to use a persistent Daytona session per conversation and
  sandbox, so shell state survives across tool calls.
- Fix `start_service` so it actually honors `cwd`, accepts `env_vars`, and uses
  SDK-supported async execution semantics.
- Add an LLM-visible text-file ingress path for `run_code` and `run_command`
  that does not rely only on Dify `file` / `files` parameters.
- Remove agent-hostile tool `LOG` outputs from agent-facing tools and standardize
  on concise text and structured JSON observations.
- Make sandbox reuse deterministic by preferring explicit IDs and
  conversation-labeled sandboxes only.
- Prefer signed preview URLs for private sandboxes and keep raw token-style
  behavior explicit.
- Add `env_vars` support to `run_code` so the plugin uses Daytona interpreter
  and code-run environment overrides.
- Update README, tool YAML descriptions, and agent guidance so the documented
  behavior matches the real implementation.

## Capabilities

### New Capabilities
- `daytona-sandbox-tools`: reliable session-backed command execution, corrected
  service startup context, agent-compatible text-file ingress, environment
  overrides, and signed preview support.
- `dify-agent-compatibility`: deterministic sandbox selection, agent-safe tool
  observations, FunctionCalling-first guidance, and documentation of Dify Agent
  file-parameter constraints.

### Modified Capabilities
- None.

## Impact

- Affected code: `_client.py`, `run_command`, `run_code`, `start_service`,
  `get_preview_url`, selected tool YAML files, README, and agent prompt docs.
- Affected runtime behavior: sandbox resolution, command execution model,
  service startup behavior, preview generation, and agent-facing file ingress.
- Dependencies/systems: Daytona SDK `0.187.0`, Dify Plugin SDK `0.9.0`, and the
  official `langgenius/agent` marketplace plugin.
