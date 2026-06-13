# Delta for Dify Agent Compatibility

## ADDED Requirements

### Requirement: Function Calling compatibility

The Daytona tool provider SHALL expose tool schemas that are suitable for Dify's Function Calling agent strategy.

#### Scenario: Model selects repository workflow tools

- GIVEN a Function Calling agent has access to the Daytona tools
- WHEN the user asks the agent to inspect or modify a Git repository
- THEN the tool schemas SHALL make the intended workflow clear through tool names, parameter names, and LLM descriptions
- AND the agent SHALL be able to choose clone, list/search, read, write, and execute tools without relying on shell-only file operations

#### Scenario: Required parameters are clear

- GIVEN a Function Calling agent chooses a Daytona tool
- WHEN the model constructs tool arguments
- THEN all LLM-provided required parameters SHALL have clear descriptions and examples
- AND secret/runtime-only values SHALL not be required from the LLM

### Requirement: ReAct observation compatibility

The Daytona tool provider SHALL return concise, bounded observations that work in Dify's ReAct strategy loop.

#### Scenario: Tool returns large result set

- GIVEN a ReAct agent invokes a filesystem discovery tool on a large repository
- WHEN the result set exceeds the configured maximum
- THEN the text observation SHALL summarize the result and truncation
- AND the JSON payload SHALL include structured results and `truncated` metadata

#### Scenario: Tool returns generated artifact

- GIVEN a Daytona tool returns a blob, image, or link
- WHEN Dify Agent forwards the tool response
- THEN the tool SHALL also include enough text or JSON context for the LLM to explain the result to the user

### Requirement: Secret-safe agent observations

The Daytona tool provider SHALL not return raw secrets in tool observations that Dify Agent may pass back into LLM context.

#### Scenario: Git credentials are used

- GIVEN an agent invokes `git_clone` with a private repository token
- WHEN the tool returns its observation
- THEN the observation SHALL not contain the token
- AND SHALL not contain credential-bearing URLs

#### Scenario: Preview token exists

- GIVEN Daytona returns a preview token
- WHEN `get_preview_url` returns its default observation
- THEN the raw token SHALL not be included by default

### Requirement: Minimal tool surface for agent reliability

The Daytona provider SHALL expose a compact set of high-value tools rather than every Daytona SDK feature.

#### Scenario: Agent receives Daytona tool list

- GIVEN a Dify Agent is configured with the Daytona provider tools
- WHEN the agent plans a code execution task
- THEN the tool set SHALL include lifecycle, file discovery, file read/write, code/command execution, artifact retrieval, preview, and cleanup capabilities
- AND SHALL avoid PTY, LSP, MCP, GPU, volume, and full Git workflow tools unless a future change provides a concrete use case

## MODIFIED Requirements

### Requirement: Tool descriptions guide safe usage

Tool descriptions SHALL guide agents toward safe and robust Daytona SDK operations instead of shell hacks for structured operations.

#### Scenario: Agent needs to write a file

- GIVEN an agent needs to create or replace a text file in a sandbox
- WHEN the agent reviews available tools
- THEN `write_file` SHALL be described as the preferred tool for text file writes
- AND `run_command` SHALL remain available for commands and tests rather than being required for shell-escaped file creation

#### Scenario: Agent needs to inspect a file

- GIVEN an agent needs to inspect a source file in a cloned repository
- WHEN the agent reviews available tools
- THEN `read_file` SHALL be described as the preferred tool for bounded text file inspection
- AND `download_file` SHALL be described as artifact retrieval for user-facing blobs/downloads
