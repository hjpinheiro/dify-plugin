# Delta for Dify Agent Compatibility

## ADDED Requirements

### Requirement: Backward-compatible deprecation of redundant tools

When the plugin consolidates redundant tools, it SHALL keep the superseded tools
registered and functional for one release and mark them as deprecated, so
existing agent configurations do not break.

#### Scenario: Deprecated lifecycle tools still work

- GIVEN an agent already configured with `start_sandbox`, `stop_sandbox`, or
  `archive_sandbox`
- WHEN the agent invokes one of those tools in this release
- THEN the tool SHALL perform its action exactly as before

#### Scenario: Deprecated tools steer the model to the replacement

- GIVEN the consolidated `manage_sandbox` tool exists
- WHEN the model reads the descriptions of `start_sandbox`, `stop_sandbox`, and
  `archive_sandbox`
- THEN each description SHALL indicate it is deprecated and point to
  `manage_sandbox`

#### Scenario: Removal is deferred

- GIVEN the deprecated lifecycle tools
- WHEN this release ships
- THEN the deprecated tools SHALL remain available
- AND their removal SHALL be deferred to a later, separately versioned release

## MODIFIED Requirements

### Requirement: Minimal tool surface for agent reliability

The Daytona provider SHALL expose a compact set of high-value tools and SHALL add
new tools only when they enable a distinct, high-value workflow, preferring
additive changes that do not break installed agent configurations, AND SHALL
consolidate redundant tools behind a single interface while retaining
irreversible operations as separate, explicitly named tools.

#### Scenario: Agent receives Daytona tool list

- GIVEN a Dify Agent is configured with the Daytona provider tools
- WHEN the agent plans a code execution task
- THEN the tool set SHALL include consolidated lifecycle management
  (`manage_sandbox` for start/stop/archive), a separate `destroy_sandbox`, file
  discovery, file read/write, code/command execution, background service
  execution, artifact retrieval, preview, and listing capabilities
- AND SHALL avoid PTY, LSP, MCP, GPU, volume, computer-use, SSH, and full Git
  workflow tools unless a future change provides a concrete use case

#### Scenario: Irreversible operations stay explicit

- GIVEN sandbox destruction is irreversible
- WHEN lifecycle tools are consolidated
- THEN destruction SHALL remain a separate `destroy_sandbox` tool
- AND SHALL NOT be reachable as an action of the consolidated lifecycle tool

#### Scenario: Existing tool names are preserved

- GIVEN agents already configured with the current tool names
- WHEN this change adds `manage_sandbox`
- THEN existing tool names, parameters, and default behaviors SHALL be preserved
- AND new capabilities SHALL be additive
