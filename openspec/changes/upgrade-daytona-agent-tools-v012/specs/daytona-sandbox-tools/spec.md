# Delta for Daytona Sandbox Tools

## ADDED Requirements

### Requirement: Consolidated sandbox lifecycle management

The plugin SHALL provide a single `manage_sandbox` tool that performs sandbox
state transitions (`start`, `stop`, `archive`) selected by an `action` parameter,
so agents can manage lifecycle through one tool instead of three near-identical
tools.

#### Scenario: Start via manage_sandbox

- GIVEN a sandbox in the `stopped` or `archived` state
- WHEN `manage_sandbox` is invoked with `action=start`
- THEN the plugin SHALL start the sandbox and wait until it is started
- AND return JSON including `sandbox_id`, `action`, and the resulting state

#### Scenario: Stop via manage_sandbox

- GIVEN a sandbox in the `started` state
- WHEN `manage_sandbox` is invoked with `action=stop`
- THEN the plugin SHALL stop the sandbox without first starting it
- AND return JSON including `sandbox_id`, `action`, and the resulting state

#### Scenario: Archive via manage_sandbox

- GIVEN a sandbox that can be archived
- WHEN `manage_sandbox` is invoked with `action=archive`
- THEN the plugin SHALL archive the sandbox
- AND return JSON including `sandbox_id`, `action`, and the resulting state

#### Scenario: Invalid action is rejected

- GIVEN any sandbox
- WHEN `manage_sandbox` is invoked with an `action` other than `start`, `stop`,
  or `archive`
- THEN the plugin SHALL fail with a clear error and SHALL NOT change sandbox state

#### Scenario: Sandbox resolved from active sandbox

- GIVEN a conversation has a stored active sandbox
- WHEN `manage_sandbox` is invoked without `sandbox_id`
- THEN the plugin SHALL use the active sandbox
- AND fail with a clear error when no sandbox is available

#### Scenario: Destroy is not part of manage_sandbox

- GIVEN an agent intends to permanently delete a sandbox
- WHEN it inspects the available tools
- THEN destruction SHALL remain a separate `destroy_sandbox` tool
- AND `manage_sandbox` SHALL NOT accept a destroy action

### Requirement: Configurable execution timeout

The `run_code`, `run_command`, and `git_clone` tools SHALL accept an optional
`timeout` (seconds) so long-running operations can complete, clamped to a safe
maximum, with omission preserving current default behavior.

#### Scenario: Extend timeout for a long command

- GIVEN a command expected to run longer than the default timeout
- WHEN `run_command` is invoked with an explicit `timeout` within the allowed
  maximum
- THEN the plugin SHALL apply that timeout to the execution
- AND allow the command to run up to the requested bound

#### Scenario: Timeout omitted preserves default

- GIVEN `run_code`, `run_command`, or `git_clone` is invoked without `timeout`
- WHEN the operation runs
- THEN the plugin SHALL use the existing default behavior unchanged

#### Scenario: Timeout above the maximum is clamped

- GIVEN a caller supplies a `timeout` greater than the configured maximum
- WHEN the tool resolves the timeout
- THEN the plugin SHALL clamp it to the maximum
- AND SHALL NOT allow an unbounded execution

#### Scenario: Git clone exceeds its timeout

- GIVEN `git_clone` is invoked with a `timeout` and the clone exceeds it
- WHEN the bound is reached
- THEN the plugin SHALL surface a clear, timeout-aware error
- AND SHALL NOT hang indefinitely

### Requirement: Memory-bounded file reading

The `read_file` tool SHALL avoid downloading an entire large file when only a
bounded head is requested, by checking the file size before downloading.

#### Scenario: Read the head of an oversized file

- GIVEN a file whose size exceeds the full-download guard and exceeds `max_bytes`
- WHEN `read_file` is invoked
- THEN the plugin SHALL NOT download the entire file into memory
- AND SHALL return a clear result reporting the file size, marking the content as
  truncated, and instructing the agent to use `download_file` or raise `max_bytes`

#### Scenario: Read a small file

- GIVEN a file within the full-download guard
- WHEN `read_file` is invoked
- THEN the plugin SHALL download the file, truncate to `max_bytes` when needed,
  and decode the content as UTF-8 with replacement for invalid bytes

## MODIFIED Requirements

### Requirement: Preview URL token handling

The `get_preview_url` tool SHALL avoid exposing preview tokens to the LLM by
default, SHALL support time-limited signed preview URLs where the SDK provides
them, AND SHALL produce correct results when a preview proxy domain is configured
for private sandboxes.

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

#### Scenario: Proxied preview of a public sandbox

- GIVEN a public sandbox and a configured preview proxy domain
- WHEN `get_preview_url` is invoked
- THEN the tool SHALL return the proxied URL rewritten through the proxy domain
- AND the proxied URL SHALL work without a token

#### Scenario: Proxied preview of a private sandbox

- GIVEN a private (token-required) sandbox and a configured preview proxy domain
- WHEN `get_preview_url` is invoked
- THEN the tool SHALL either propagate the preview token so the proxy can present
  it to the Daytona edge, OR return the proxied URL together with an explicit
  warning that the proxy must inject the preview token
- AND SHALL include a hint that creating the sandbox as public avoids the
  requirement
- AND SHALL NOT silently return a proxied URL that will fail authentication
