## ADDED Requirements

### Requirement: Session-backed command execution

The `run_command` tool SHALL execute commands through a persistent Daytona
session scoped to the current conversation and sandbox, so shell state can
survive across tool calls.

#### Scenario: Directory change persists across calls
- **GIVEN** a persistent sandbox exists for the conversation
- **WHEN** `run_command` executes `cd /home/daytona/repo`
- **AND** a later `run_command` executes `pwd` in the same conversation and
  sandbox
- **THEN** the second command SHALL run in `/home/daytona/repo`
- **AND** the plugin SHALL NOT require the agent to repeat `cd ... &&` in every
  call

#### Scenario: Per-call working directory override
- **GIVEN** a persistent command session already exists
- **WHEN** `run_command` is invoked with `cwd="/tmp"` and `command="pwd"`
- **THEN** the command SHALL execute in `/tmp`
- **AND** the plugin SHALL apply that override by composing the shell command
- **AND** the plugin SHALL NOT depend on unsupported SDK request fields

#### Scenario: Streaming command uses supported async session execution
- **GIVEN** `run_command` is invoked with `stream=true`
- **WHEN** the command starts
- **THEN** the plugin SHALL use the SDK-supported async session execution flag
- **AND** SHALL stream stdout and stderr until completion or timeout

#### Scenario: Missing session is recreated transparently
- **GIVEN** a sandbox exists but the shared command session no longer exists
- **WHEN** `run_command` is invoked
- **THEN** the plugin SHALL recreate the shared session automatically
- **AND** SHALL continue executing the command in the sandbox

### Requirement: Service startup honors execution context

The `start_service` tool SHALL apply its requested execution context correctly.

#### Scenario: Service starts from requested working directory
- **GIVEN** a sandbox contains an application under `/home/daytona/app`
- **WHEN** `start_service` is invoked with `cwd="/home/daytona/app"`
- **THEN** the background process SHALL start from that directory
- **AND** the plugin SHALL NOT ignore the `cwd` parameter

#### Scenario: Service receives environment variables
- **GIVEN** `start_service` is invoked with `env_vars`
- **WHEN** the process starts
- **THEN** the service process SHALL receive those environment variables
- **AND** the plugin SHALL apply them through supported Daytona execution
  semantics

#### Scenario: Service result includes preview metadata when port is known
- **GIVEN** `start_service` is invoked with a `port`
- **WHEN** the service starts successfully
- **THEN** the JSON result SHALL include enough preview metadata for the agent to
  continue reliably
- **AND** `get_preview_url` SHALL remain available as a separate tool

### Requirement: Agent-compatible text file ingress

The `run_code` and `run_command` tools SHALL support LLM-visible text-based file
ingress without relying only on Dify `file` / `files` parameters.

#### Scenario: Multiple text files are injected before execution
- **GIVEN** `run_command` or `run_code` is invoked with `input_text_files`
- **WHEN** the JSON payload maps workspace-relative paths to text content
- **THEN** the plugin SHALL write each file under `/home/daytona/workspace/`
- **AND** the execution SHALL run after those files are created
- **AND** the JSON result SHALL list the created paths in `uploaded_files`

#### Scenario: Path traversal is rejected
- **GIVEN** `input_text_files` contains `../` or an absolute path outside the
  workspace root
- **WHEN** the tool validates the input
- **THEN** the plugin SHALL fail with a clear error
- **AND** SHALL NOT write the file outside the workspace

#### Scenario: Existing workflow file inputs still work
- **GIVEN** a workflow or form-based caller provides existing `input_files`
- **WHEN** `run_code` or `run_command` executes
- **THEN** the plugin SHALL preserve the existing `input_files` behavior
- **AND** SHALL treat `input_text_files` as an additive capability

### Requirement: Code execution environment overrides

The `run_code` tool SHALL expose Daytona environment override support.

#### Scenario: Stateful Python execution receives environment variables
- **GIVEN** `run_code` is invoked with `stateful=true` and `env_vars`
- **WHEN** the code runs through `code_interpreter`
- **THEN** those environment variables SHALL be visible to the Python process

#### Scenario: Stateless execution receives environment variables
- **GIVEN** `run_code` is invoked with `stateful=false` and `env_vars`
- **WHEN** the code runs through `process.code_run`
- **THEN** those environment variables SHALL be visible to the executed code

### Requirement: Signed preview URLs for private sandboxes

The `get_preview_url` tool SHALL prefer self-contained signed preview URLs for
private sandboxes and SHALL keep raw token-style behavior explicit.

#### Scenario: Public sandbox preview
- **GIVEN** a public sandbox exposes a service on a supported port
- **WHEN** `get_preview_url` is invoked
- **THEN** the tool SHALL return a working preview URL
- **AND** SHALL NOT expose raw preview token details by default

#### Scenario: Private sandbox preview uses a signed URL
- **GIVEN** a private sandbox requires preview authorization
- **WHEN** `get_preview_url` is invoked with default behavior
- **THEN** the plugin SHALL prefer a signed preview URL
- **AND** the returned URL SHALL be directly usable without a separate token
  header

#### Scenario: Proxied signed preview preserves query parameters
- **GIVEN** a signed preview URL contains authorization query parameters
- **AND** a preview proxy domain is configured
- **WHEN** the URL is rewritten through the proxy
- **THEN** the rewritten URL SHALL preserve the query string unchanged
- **AND** SHALL NOT silently discard the authorization data needed for the
  preview
