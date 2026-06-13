## ADDED Requirements

### Requirement: Stateful Python code execution

The provider SHALL support stateful interactive Python execution using the
Daytona SDK `code_interpreter` API, preserving variable namespace, imports,
and function definitions across sequential tool calls within the same sandbox.

#### Scenario: Variable persists across turns

- GIVEN a persistent sandbox exists
- WHEN `run_code` is called with `stateful=true` and code `x = 42`
- AND a subsequent call runs `print(x)` with `stateful=true`
- THEN the output SHALL contain `42`
- AND SHALL NOT raise `NameError`

#### Scenario: Stateless fallback for non-Python

- GIVEN `run_code` is called with `language="typescript"`
- WHEN `stateful=true` is set
- THEN the plugin SHALL fall back to `process.code_run()` (existing behavior)
- AND SHALL NOT attempt to use `code_interpreter`

#### Scenario: Error traceback surfaced

- GIVEN `run_code` is called with `stateful=true` and code that raises
- WHEN execution completes with an error
- THEN the JSON response SHALL include `error.name`, `error.value`, and
  `error.traceback`
- AND the text message SHALL clearly describe the error

#### Scenario: Explicit stateless mode

- GIVEN `run_code` is called with `stateful=false`
- WHEN the code executes
- THEN the plugin SHALL use `process.code_run()` (existing behavior)
- AND chart artifact extraction SHALL work as before
