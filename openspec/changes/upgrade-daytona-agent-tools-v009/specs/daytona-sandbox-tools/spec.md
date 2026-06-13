# Delta for Daytona Sandbox Tools

## ADDED Requirements

### Requirement: Transparent reactivation of idle sandboxes

The plugin SHALL transparently reactivate a stopped or archived sandbox before a
tool uses it, so that reusing a sandbox across turns does not fail due to the
sandbox's idle state.

#### Scenario: Reuse a stopped sandbox

- GIVEN a sandbox that has auto-stopped and is in the `stopped` state
- WHEN a tool that needs to execute code, run a command, or access files is
  invoked with that sandbox ID
- THEN the plugin SHALL start the sandbox and wait until it is started
- AND then perform the requested operation successfully

#### Scenario: Reuse an archived sandbox

- GIVEN a sandbox in the `archived` state
- WHEN a tool that needs the sandbox is invoked with that sandbox ID
- THEN the plugin SHALL restore and start the sandbox
- AND then perform the requested operation successfully

#### Scenario: Sandbox is in an unusable state

- GIVEN a sandbox in an `error`, `destroyed`, or `destroying` state
- WHEN a tool is invoked with that sandbox ID
- THEN the plugin SHALL fail with a clear error describing the state
- AND SHALL NOT attempt to execute the operation

#### Scenario: State value is read defensively

- GIVEN the Daytona SDK returns sandbox state as an enum whose value is a string
- WHEN the plugin evaluates whether to reactivate the sandbox
- THEN the plugin SHALL read the state defensively and compare it
  case-insensitively

### Requirement: Background service execution

The plugin SHALL provide a way to start a long-running process in a sandbox
without blocking, so that services can run while the agent continues and their
preview URLs can be retrieved.

#### Scenario: Start a background service

- GIVEN an existing or active sandbox
- WHEN the agent starts a long-running service with the background execution tool
- THEN the plugin SHALL launch the command asynchronously in a sandbox session
- AND return immediately with a session identifier and command identifier
- AND SHALL NOT block until the service exits

#### Scenario: Retrieve service logs

- GIVEN a background command was started in a session
- WHEN the agent requests logs for that session and command
- THEN the plugin SHALL return a bounded amount of recent log output
- AND clearly indicate when output was truncated

#### Scenario: Background service paired with preview URL

- GIVEN a background service is listening on a supported port
- WHEN the agent calls the preview URL tool for that port
- THEN the plugin SHALL return a working preview URL for the running service

### Requirement: Sandbox lifecycle controls

The plugin SHALL provide tools to start, stop, and archive a sandbox so agents
can manage sandbox cost and persistence without destroying state.

#### Scenario: Stop a running sandbox

- GIVEN a sandbox in the `started` state
- WHEN the stop tool is invoked with its sandbox ID
- THEN the plugin SHALL stop the sandbox
- AND return JSON including `sandbox_id` and the resulting state

#### Scenario: Start a stopped sandbox

- GIVEN a sandbox in the `stopped` state
- WHEN the start tool is invoked with its sandbox ID
- THEN the plugin SHALL start the sandbox
- AND return JSON including `sandbox_id` and the resulting state

#### Scenario: Archive a stopped sandbox

- GIVEN a sandbox that can be archived
- WHEN the archive tool is invoked with its sandbox ID
- THEN the plugin SHALL archive the sandbox
- AND return JSON including `sandbox_id` and the resulting state

#### Scenario: Stop does not pre-start the sandbox

- GIVEN a sandbox that is not currently started
- WHEN the stop tool is invoked
- THEN the plugin SHALL NOT first start the sandbox in order to stop it

### Requirement: Chart artifact metadata in code execution

The `run_code` tool SHALL return chart metadata alongside chart image blobs so
the agent can describe generated visualizations.

#### Scenario: Code produces a matplotlib chart

- GIVEN code that generates one or more matplotlib charts
- WHEN `run_code` executes the code
- THEN the tool SHALL yield each chart image as a blob message
- AND include chart metadata (such as type and title when available) in the JSON
  output
- AND include a chart count in the JSON output

#### Scenario: Code produces no charts

- GIVEN code that generates no charts
- WHEN `run_code` executes the code
- THEN the tool SHALL still return output and exit code without error
- AND report a chart count of zero

### Requirement: Packaging validation gate

The packaging process SHALL validate plugin metadata before producing a release
artifact, to prevent shipping an unbuildable or inconsistent package.

#### Scenario: Invalid YAML blocks packaging

- GIVEN any of `manifest.yaml`, `provider/*.yaml`, or `tools/*.yaml` does not
  parse as valid YAML
- WHEN the packaging step runs
- THEN packaging SHALL fail with a non-zero exit and a clear error
- AND SHALL NOT produce a release artifact

#### Scenario: Manifest version consistency

- GIVEN the manifest is being packaged
- WHEN the packaging step validates it
- THEN there SHALL be a top-level `version` and a `meta.version`
- AND they SHALL be equal, otherwise packaging SHALL fail

#### Scenario: Tool registration consistency

- GIVEN the provider registers a list of tools
- WHEN the packaging step validates the package
- THEN every registered tool SHALL have a matching tool YAML and Python source
  file, otherwise packaging SHALL fail

#### Scenario: Archive contains files only

- GIVEN the package archive is generated
- WHEN the packaging step inspects it
- THEN the archive SHALL contain files only with no directory entries

## MODIFIED Requirements

### Requirement: Preview URL token handling

The `get_preview_url` tool SHALL avoid exposing preview tokens to the LLM by
default, and SHALL support time-limited signed preview URLs where the SDK
provides them.

#### Scenario: Get preview URL with default parameters

- GIVEN an existing sandbox running a service on a supported port
- WHEN `get_preview_url` is invoked without an explicit token opt-in
- THEN the tool SHALL return the preview URL, port, and sandbox ID
- AND SHALL NOT return the raw preview token in the default JSON output

#### Scenario: Explicit token opt-in

- GIVEN a caller explicitly requests token details
- WHEN `get_preview_url` returns token metadata
- THEN the tool SHALL make token exposure explicit in the tool contract
- AND documentation SHALL explain that private previews require the token header

#### Scenario: Signed preview URL

- GIVEN a caller needs to share a time-limited preview
- WHEN a signed preview URL is requested and supported by the SDK
- THEN the plugin SHALL return a signed URL with a bounded lifetime
- AND SHALL NOT require exposing the raw preview token
