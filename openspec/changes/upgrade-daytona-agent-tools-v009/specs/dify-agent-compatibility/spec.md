# Delta for Dify Agent Compatibility

## ADDED Requirements

### Requirement: Active sandbox memory across tool calls

The plugin SHALL remember the active sandbox for a conversation so agents do not
have to pass `sandbox_id` to every tool.

#### Scenario: Create then reuse without repeating the ID

- GIVEN an agent creates a sandbox in one tool call
- WHEN a subsequent tool that needs a sandbox is invoked without `sandbox_id`
- THEN the plugin SHALL use the conversation's active sandbox
- AND perform the requested operation against it

#### Scenario: Explicit sandbox ID overrides stored active sandbox

- GIVEN a conversation has a stored active sandbox
- WHEN a tool is invoked with an explicit `sandbox_id`
- THEN the plugin SHALL use the explicit `sandbox_id`
- AND SHALL NOT use the stored active sandbox

#### Scenario: No sandbox available

- GIVEN a conversation has no stored active sandbox
- WHEN a tool that needs a sandbox is invoked without `sandbox_id`
- THEN the plugin SHALL fail with a clear error instructing the agent to create
  or specify a sandbox

#### Scenario: Active sandbox cleared on destroy

- GIVEN the stored active sandbox is destroyed
- WHEN `destroy_sandbox` completes for that sandbox ID
- THEN the plugin SHALL clear the stored active sandbox

#### Scenario: Storage failures are non-fatal

- GIVEN session storage is unavailable or fails
- WHEN a tool reads or writes the active sandbox
- THEN the plugin SHALL treat the situation as "no active sandbox"
- AND SHALL NOT fail the primary operation because of storage errors

#### Scenario: No credentials are stored

- GIVEN the plugin persists conversation state
- WHEN it writes to session storage
- THEN it SHALL store only the sandbox identifier
- AND SHALL NOT store API keys or other credentials

### Requirement: Workflow-friendly variable outputs

Key tools SHALL emit named output variables so the plugin can be chained inside
Dify Workflows.

#### Scenario: Sandbox creation exposes a variable

- GIVEN a Workflow node invokes `create_sandbox`
- WHEN the sandbox is created
- THEN the tool SHALL emit a named `sandbox_id` output variable
- AND SHALL still emit its existing text and JSON messages

#### Scenario: Execution exposes result variables

- GIVEN a Workflow node invokes `run_code` or `run_command` against a persistent
  sandbox
- WHEN execution completes
- THEN the tool SHALL emit named output variables for the sandbox ID and exit
  code
- AND SHALL still emit its existing text and JSON messages

#### Scenario: Preview URL exposes a variable

- GIVEN a Workflow node invokes `get_preview_url`
- WHEN the preview URL is generated
- THEN the tool SHALL emit a named `preview_url` output variable

### Requirement: Progress visibility for long operations

Long-running tools SHALL emit structured log messages so users get progress
feedback in the Dify UI.

#### Scenario: Sandbox creation shows progress

- GIVEN `create_sandbox` may take a long time
- WHEN it runs
- THEN the tool SHALL emit a start log message and a finish log message
- AND the final result messages SHALL remain unchanged

#### Scenario: Git clone shows progress

- GIVEN `git_clone` may take a long time on large repositories
- WHEN it runs
- THEN the tool SHALL emit start and finish log messages

## MODIFIED Requirements

### Requirement: Minimal tool surface for agent reliability

The Daytona provider SHALL expose a compact set of high-value tools and SHALL add
new tools only when they enable a distinct, high-value workflow, preferring
additive changes that do not break installed agent configurations.

#### Scenario: Agent receives Daytona tool list

- GIVEN a Dify Agent is configured with the Daytona provider tools
- WHEN the agent plans a code execution task
- THEN the tool set SHALL include lifecycle (create/start/stop/archive/destroy),
  file discovery, file read/write, code/command execution, background service
  execution, artifact retrieval, preview, and listing capabilities
- AND SHALL avoid PTY, LSP, MCP, GPU, volume, computer-use, SSH, and full Git
  workflow tools unless a future change provides a concrete use case

#### Scenario: Existing tool names are preserved

- GIVEN agents already configured with the current tool names
- WHEN this change adds new tools
- THEN existing tool names, parameters, and default behaviors SHALL be preserved
- AND new capabilities SHALL be additive
