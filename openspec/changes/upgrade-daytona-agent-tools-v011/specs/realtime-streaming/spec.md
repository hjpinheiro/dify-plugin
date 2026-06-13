## ADDED Requirements

### Requirement: Real-time command output streaming

The provider SHALL support optional streaming mode for `run_command` that
delivers stdout and stderr chunks to the Dify UI incrementally as they are
produced, rather than blocking until process completion.

#### Scenario: Streaming a long build command

- GIVEN `run_command` is called with `stream=true` and a long-running command
- WHEN the command produces output
- THEN the plugin SHALL yield text messages incrementally
- AND SHALL NOT buffer all output until the process exits

#### Scenario: Non-streaming default is unchanged

- GIVEN `run_command` is called without `stream` or with `stream=false`
- WHEN the command executes
- THEN the plugin SHALL use blocking `process.exec()` (existing behavior)
- AND SHALL return the full output in a single response

#### Scenario: Streaming timeout

- GIVEN a streaming command exceeds `EXECUTION_TIMEOUT` (120s)
- WHEN the timeout is reached
- THEN the plugin SHALL yield a timeout warning message
- AND SHALL include partial output collected so far

#### Scenario: Streaming completion

- GIVEN a streaming command finishes
- WHEN the process exits
- THEN the plugin SHALL yield a final JSON message with `exit_code`
- AND SHALL yield a final text message with the complete output summary
