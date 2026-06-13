# Delta for Dify Agent Compatibility

## ADDED Requirements

### Requirement: Removal of redundant lifecycle tools

The plugin SHALL remove superseded lifecycle tools (`start_sandbox`,
`stop_sandbox`, `archive_sandbox`) in favor of the consolidated
`manage_sandbox` tool, reducing the tool surface for better agent reliability.

#### Scenario: Redundant lifecycle tools are not registered

- GIVEN the consolidated `manage_sandbox` tool exists
- WHEN the provider YAML is loaded
- THEN `start_sandbox`, `stop_sandbox`, and `archive_sandbox` SHALL NOT be
  registered as tools

#### Scenario: manage_sandbox covers all removed functionality

- GIVEN the three lifecycle tools were removed
- WHEN an agent needs to start, stop, or archive a sandbox
- THEN `manage_sandbox(action="start"|"stop"|"archive")` SHALL provide the
  same functionality

#### Scenario: Irreversible destroy stays separate

- GIVEN sandbox destruction is irreversible
- WHEN lifecycle tools are consolidated
- THEN destruction SHALL remain a separate `destroy_sandbox` tool
- AND SHALL NOT be reachable as an action of `manage_sandbox`

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
