# Proposal: Upgrade Daytona Dify Agent Tools v0.0.6

## Intent

Improve the Daytona Dify plugin so it is reliable to configure, safer to use from Dify Agent strategies, and more useful for repository-based agent workflows.

The current plugin already exposes core sandbox lifecycle, code execution, command execution, file transfer, file search, Git clone, preview URL, and sandbox listing tools. This change targets the next focused release by fixing SDK compatibility issues, adding the minimum missing file-editing primitives agents need, tightening output and secret handling, and aligning documentation with actual behavior.

## Motivation

- Provider credential validation currently calls the Daytona SDK with an invalid `daytona.list(limit=1)` signature for SDK v0.187.
- Agents can clone and search repositories but cannot reliably read or write text files without falling back to shell commands.
- Some tool outputs can grow without bounds, which harms Dify Agent reasoning loops and can exceed context limits.
- Git and preview credentials/tokens need clearer handling because Dify Agent strategies pass tool observations back into the LLM.
- Dependency ranges and the lockfile are inconsistent with the SDK version used during validation.
- The README no longer reflects the current 12-tool implementation and combined-output behavior.

## Scope

This change includes:

- Fix Daytona provider credential validation against the official SDK API.
- Pin or constrain dependencies to the tested Daytona SDK family.
- Add `read_file` and `write_file` tools for agent-safe text file access.
- Add bounded outputs and truncation metadata to filesystem search/list tools.
- Harden file download and upload size checks.
- Improve `git_clone` post-clone verification using Git status when available.
- Treat Git password/token as a non-LLM runtime input.
- Improve ephemeral sandbox creation semantics for one-off execution.
- Expose a small set of sandbox creation controls that map to official Daytona SDK capabilities.
- Update README, manifest/provider tool lists, package metadata, and generated package validation.

## Out Of Scope

- Full PTY/session support.
- LSP tools.
- Daytona MCP server integration.
- Volume management.
- GPU scheduling controls.
- Full Git workflow tools such as push, commit, branch management, and pull, except where explicitly added as future work.
- Converting this tool provider into a Dify Agent Strategy plugin.

## Success Criteria

- Dify can validate Daytona provider credentials successfully with SDK v0.187.
- A Dify Agent can clone a repository, list files, read files, edit/write files, run commands/tests, and return generated artifacts without shell quoting hacks for basic file operations.
- Large filesystem outputs are bounded and include `truncated` metadata.
- Secret inputs are not exposed as LLM-generated parameters or returned in tool outputs.
- The package installs in Dify with the expected tool list and no signature/packaging regressions.
- Documentation accurately describes available tools, parameters, and return values.

## References

- Daytona Python SDK v0.187 docs and local SDK inspection.
- Dify official Agent strategies plugin (`langgenius/agent`) Function Calling and ReAct behavior.
- Existing plugin code in `hjpinheiro/dify-plugin` v0.0.5.
