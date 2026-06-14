## ADDED Requirements

### Requirement: Deterministic sandbox selection for agents

Sandbox resolution SHALL be deterministic and conversation-safe for autonomous
agent execution.

#### Scenario: Explicit sandbox ID wins
- **GIVEN** a conversation already has an active sandbox
- **WHEN** an agent invokes a tool with an explicit `sandbox_id`
- **THEN** the plugin SHALL use the explicit sandbox
- **AND** SHALL NOT replace it with any automatically discovered sandbox

#### Scenario: Conversation-labeled sandbox is reused
- **GIVEN** a conversation has a sandbox labeled for that conversation
- **WHEN** an agent invokes a sandbox-dependent tool without `sandbox_id`
- **THEN** the plugin SHALL reuse the conversation-labeled sandbox
- **AND** SHALL perform the requested operation in that sandbox

#### Scenario: Unlabeled sandbox is not auto-claimed
- **GIVEN** the account contains an unlabeled sandbox unrelated to the
  conversation
- **WHEN** an agent invokes a sandbox-dependent tool without `sandbox_id`
- **THEN** the plugin SHALL NOT auto-claim the unlabeled sandbox
- **AND** SHALL either use the conversation sandbox or fail clearly

#### Scenario: Execution tools fall back to ephemeral only when supported
- **GIVEN** no conversation sandbox exists
- **WHEN** `run_code` or `run_command` is invoked without `sandbox_id`
- **THEN** those tools MAY create an ephemeral sandbox
- **AND** tools that require an existing sandbox SHALL fail with a clear error
  instead

### Requirement: Agent-safe observation contract

Agent-facing tools SHALL return observations that work well in Dify's official
FunctionCalling and ReAct strategies.

#### Scenario: Tool does not emit `LOG` messages into the agent loop
- **GIVEN** the official marketplace `langgenius/agent` plugin is invoking
  Daytona tools
- **WHEN** an agent uses `create_sandbox`, `git_clone`, `start_service`, or
  `auto_expose`
- **THEN** the Daytona tool SHALL NOT rely on `ToolInvokeMessage.LOG` for its
  observation contract
- **AND** the agent-visible result SHALL be expressed through concise text and
  JSON

#### Scenario: Tool result is concise and structured
- **GIVEN** an agent invokes a Daytona tool
- **WHEN** the tool completes
- **THEN** the tool SHALL return a bounded text observation suitable for
  immediate reasoning
- **AND** SHALL also return structured JSON for machine-readable detail

#### Scenario: Service startup result is actionable
- **GIVEN** an agent invokes `start_service`
- **WHEN** the service starts successfully
- **THEN** the returned observation SHALL include enough information for the next
  action
- **AND** SHALL not require the agent to infer missing execution context such as
  whether `cwd` or `env_vars` were applied

#### Scenario: Tool descriptions do not over-promise behavior
- **GIVEN** an agent reads the Daytona tool descriptions
- **WHEN** it plans a workflow
- **THEN** the descriptions SHALL match the real Python implementation
- **AND** SHALL NOT claim ephemeral creation or other behavior that the tool does
  not actually perform

### Requirement: Agent-compatible file ingress surface

The provider SHALL expose at least one LLM-visible file ingress path that does
not depend only on Dify `file` / `files` parameter support.

#### Scenario: Function Calling model sees a text-file ingress parameter
- **GIVEN** a FunctionCalling agent receives the Daytona tool schemas
- **WHEN** it inspects `run_code` or `run_command`
- **THEN** it SHALL see an LLM-visible parameter for text-based file ingress
- **AND** that parameter SHALL use a schema type that Dify does not strip from
  the LLM-facing tool schema

#### Scenario: Workflow file parameters remain available
- **GIVEN** a workflow or form-based caller uses `upload_file` or `input_files`
- **WHEN** the tool schema is rendered outside autonomous agent planning
- **THEN** the existing file-oriented parameters SHALL remain available
- **AND** the new agent-compatible ingress path SHALL be additive

#### Scenario: Dify limitation is documented
- **GIVEN** an operator configures the Daytona provider for autonomous agent use
- **WHEN** they read the README or agent guidance
- **THEN** the documentation SHALL explain that Dify strips `file` / `files`
  from LLM-visible tool schemas
- **AND** SHALL point to the supported text-based workaround

### Requirement: Agent operating guidance is version-aligned

The repository SHALL include agent guidance that matches the current tool
surface and runtime behavior.

#### Scenario: FunctionCalling is recommended
- **GIVEN** an operator is configuring the official `langgenius/agent` strategy
- **WHEN** they read the Daytona provider guidance
- **THEN** the guidance SHALL recommend `FunctionCalling` as the preferred
  strategy
- **AND** SHALL explain that it is the primary compatibility target for this
  plugin

#### Scenario: One sandbox per conversation is documented accurately
- **GIVEN** an operator reads the current Daytona agent prompt
- **WHEN** they follow the recommended workflow
- **THEN** the guidance SHALL describe the actual sandbox reuse rules
- **AND** SHALL reflect session-backed command execution within that sandbox
