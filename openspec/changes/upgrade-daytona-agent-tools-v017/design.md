## Context

The current plugin is feature-rich, but several workflows remain fragile when
used through the official Dify Agent plugin. The root cause is mostly contract
misalignment:

- Daytona already provides the right primitives: persistent process sessions,
  stateful Python execution, per-execution environment overrides, and signed
  preview URLs.
- The plugin does not consistently map its tools to those primitives.
- The official Dify Agent strategies handle `TEXT`, `JSON`, `LINK`, `IMAGE`,
  and `BLOB` best, but they are poor fits for tool-level `LOG` messages and do
  not expose `file` / `files` parameters to the LLM schema.
- Several YAML descriptions and guidance docs overstate behavior that the Python
  code does not actually implement.

This design keeps the provider as a Dify tool plugin and focuses on reliability
for autonomous agent execution rather than adding new low-level Daytona surfaces.

## Goals / Non-Goals

**Goals:**
- Make `run_command` reliable for multi-step agent workflows by preserving shell
  state across tool calls.
- Correct `start_service` so its runtime behavior matches its tool contract.
- Provide an agent-compatible file ingress path that survives Dify's stripping of
  `file` / `files` parameters from LLM-visible tool schemas.
- Make sandbox resolution deterministic and conversation-safe.
- Prefer Daytona signed preview URLs for private sandboxes.
- Align README, YAML, and agent guidance with real runtime behavior.

**Non-Goals:**
- Patch Dify core or the official `langgenius/agent` plugin.
- Add PTY, SSH, LSP, MCP, GPU, or other low-level Daytona SDK surfaces.
- Fully solve arbitrary binary chat-upload ingestion for autonomous agents.
- Redesign the full `create_sandbox` parameter surface in this release.

## Decisions

### 1. Use one persistent Daytona command session per conversation and sandbox

`run_command` will stop treating each call as a fresh shell. Instead, the plugin
will derive a deterministic session ID from `(conversation_id, sandbox_id)` and
reuse that Daytona session across turns.

Why:
- This is the execution model Daytona sessions are built for.
- It preserves `cd`, `export`, virtualenv activation, and other shell state.
- It reduces brittle command composition in the agent prompt.

Alternative considered:
- Keep stateless `process.exec(...)` for blocking mode and ephemeral sessions for
  streaming mode.
- Rejected because it forces the agent to keep repeating shell setup in every
  step and is the main cause of multi-step execution fragility.

### 2. Apply `cwd` and `env_vars` through command composition, not fake SDK fields

The installed Daytona SDK confirms that `SessionExecuteRequest` does not support
native `cwd` or `env` fields. The plugin will therefore compose per-call shell
wrappers such as `cd <cwd> && export KEY=VALUE && <command>` using safe quoting.

Why:
- It matches the real SDK surface.
- It makes `cwd` and `env_vars` work in both blocking and streaming session
  execution paths.

Alternative considered:
- Continue assigning `req.cwd` / `req.env` dynamically.
- Rejected because those fields are silently discarded by the SDK model.

### 3. Keep `start_service` on its own dedicated session

Long-running daemons should not share the normal command session. `start_service`
will continue using a separate session, but it will apply `cwd`, accept
`env_vars`, and use `run_async=True`.

Why:
- Background processes should not pollute the normal shell state.
- The current contract already implies a separate tracked service session.

Alternative considered:
- Reuse the shared command session.
- Rejected because service lifecycle and shell-session lifecycle are different
  concerns.

### 4. Add `input_text_files` as the agent-compatible file ingress path

The plugin will add `input_text_files` to `run_code` and `run_command` as a
string parameter containing a JSON object that maps workspace-relative file paths
to UTF-8 text content.

Why:
- Dify strips `file` / `files` from LLM-visible schemas.
- A string-based JSON payload remains visible to FunctionCalling models.
- Text-based ingress covers the most common agent tasks: scripts, config files,
  JSON fixtures, Markdown, CSV snippets, and code generation.

Alternative considered:
- Rely only on existing `input_files` / `upload_file`.
- Rejected because those paths are not dependable for autonomous Dify Agent
  planning.

### 5. Remove tool-level `LOG` messages from agent-facing tools

Agent-facing tools will standardize on concise `TEXT` plus structured `JSON`.
Tool-level `LOG` messages will be removed from the tools most likely to be used
inside the official Dify Agent loop.

Why:
- The official agent strategies reason much better over bounded text/JSON.
- Log-style tool messages add little value to autonomous reasoning and create a
  poor observation surface.

Alternative considered:
- Keep `LOG` messages for progress visibility.
- Rejected because agent reliability is more important than rich progress logs in
  this provider surface.

### 6. Prefer signed preview URLs for private sandboxes

`get_preview_url` will prefer `create_signed_preview_url(...)` for private
sandboxes and continue exposing raw token-style behavior only when explicitly
requested.

Why:
- Signed URLs are self-contained and better fit agent and user flows.
- They reduce dependence on header propagation and custom proxy handling.

Alternative considered:
- Keep only `get_preview_link(...)` and raw token semantics.
- Rejected because private preview flows remain too fragile for agents.

### 7. Make sandbox resolution deterministic

Normal sandbox resolution will stop auto-claiming arbitrary unlabeled sandboxes.
The effective order becomes: explicit ID, in-invocation memory,
conversation-labeled sandbox, then error or ephemeral behavior only for tools
that explicitly support it.

Why:
- Determinism matters more than opportunistic reuse for agent correctness.
- Unlabeled fallback can bind an agent to the wrong sandbox and create silent
  state bleed.

Alternative considered:
- Keep `find_any_sandbox(...)` fallback.
- Rejected because it is inherently non-deterministic for agent use.

## Risks / Trade-offs

- Persistent shell state may surprise users who were assuming every
  `run_command` call was stateless. → Mitigation: document the new behavior and
  make session scope explicit in README and prompt guidance.
- Removing `LOG` messages may reduce progress richness in some UIs. → Mitigation:
  keep concise text summaries and JSON results for the final observation.
- `input_text_files` improves agent compatibility but only for text payloads,
  not arbitrary binary uploads. → Mitigation: document this honestly and keep
  existing workflow-oriented binary paths.
- Deterministic sandbox resolution may stop reusing some orphaned unlabeled
  sandboxes automatically. → Mitigation: explicit `sandbox_id` remains available
  when a user wants manual control.

## Migration Plan

1. Add the new helper functions and deterministic sandbox resolution behavior.
2. Refactor `run_command` and `start_service` onto the corrected Daytona session
   model.
3. Add `input_text_files` and `env_vars` to the relevant tool YAML and Python
   implementations.
4. Switch private preview handling to signed URLs.
5. Update docs, prompt guidance, and packaging metadata.
6. Validate with `package.py`, OpenSpec validation, and targeted smoke tests.

Rollback is straightforward: revert the helper changes, restore the old command
execution path, and rebuild the package.

## Open Questions

- Whether to keep all existing `create_variable_message(...)` outputs or trim some
  of them further for agent-facing tools while preserving workflow utility.
- What default expiry is best for signed preview URLs in agent workflows.
