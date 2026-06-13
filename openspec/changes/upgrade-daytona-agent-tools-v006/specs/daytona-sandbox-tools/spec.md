# Delta for Daytona Sandbox Tools

## ADDED Requirements

### Requirement: SDK-compatible provider validation

The provider SHALL validate Daytona credentials using the official Daytona SDK method signatures supported by the pinned SDK version.

#### Scenario: Valid credentials are accepted

- GIVEN Daytona credentials with a valid API key
- WHEN Dify validates the provider credentials
- THEN the plugin SHALL create a Daytona client
- AND call sandbox listing with `ListSandboxesQuery(limit=1)` or an equivalent supported query object
- AND validation SHALL complete without SDK signature errors

#### Scenario: Invalid credentials are rejected

- GIVEN Daytona credentials with an invalid API key or API URL
- WHEN Dify validates the provider credentials
- THEN the plugin SHALL raise a provider credential validation error
- AND the error SHALL not expose secret credential values

### Requirement: Agent-readable text files

The plugin SHALL provide a `read_file` tool that returns bounded text content from a file inside a Daytona sandbox.

#### Scenario: Read a small UTF-8 file

- GIVEN an existing sandbox and a text file below the configured size limit
- WHEN `read_file` is invoked with the sandbox ID and remote path
- THEN the tool SHALL return the file content as text
- AND return JSON metadata including `sandbox_id`, `remote_path`, `size_bytes`, `encoding`, and `truncated: false`

#### Scenario: Read a large file with truncation

- GIVEN an existing sandbox and a text file larger than the requested `max_bytes`
- WHEN `read_file` is invoked with `max_bytes`
- THEN the tool SHALL return only the bounded content prefix
- AND return `truncated: true`
- AND the text observation SHALL clearly state that content was truncated

#### Scenario: File exceeds hard size limit

- GIVEN an existing sandbox and a file larger than the configured maximum allowed file size
- WHEN `read_file` is invoked
- THEN the tool SHALL fail with a clear size-limit error
- AND SHALL not download or return the full file content

### Requirement: Agent-writable text files

The plugin SHALL provide a `write_file` tool that writes text content to a file inside a Daytona sandbox without requiring shell quoting.

#### Scenario: Write text content

- GIVEN an existing sandbox
- WHEN `write_file` is invoked with a remote path and text content
- THEN the plugin SHALL upload the UTF-8 encoded content to the requested path
- AND return JSON metadata including `sandbox_id`, `remote_path`, and `size_bytes`

#### Scenario: Reject oversized content

- GIVEN text content larger than the configured maximum allowed file size
- WHEN `write_file` is invoked
- THEN the tool SHALL fail with a clear size-limit error
- AND SHALL not upload the oversized content

### Requirement: Bounded filesystem discovery outputs

Filesystem discovery tools SHALL bound list and search outputs and report truncation metadata.

#### Scenario: List directory with many entries

- GIVEN a sandbox directory containing more entries than `max_results`
- WHEN `list_files` is invoked
- THEN the tool SHALL return at most `max_results` entries
- AND return `truncated: true`
- AND include the number of entries returned

#### Scenario: Search files with many matches

- GIVEN a sandbox path containing more file name matches than `max_results`
- WHEN `search_files` is invoked
- THEN the tool SHALL return at most `max_results` paths
- AND return `truncated: true`

#### Scenario: Find in files clamps result limit

- GIVEN `find_in_files` is invoked with `max_results` above the supported maximum
- WHEN the search runs
- THEN the tool SHALL clamp `max_results` to the supported maximum
- AND return truncation metadata when more matches exist

### Requirement: Hardened file transfer size checks

File upload and download tools SHALL enforce configured file size limits before returning or storing file content.

#### Scenario: Download metadata lacks file size

- GIVEN a sandbox file whose metadata does not include a reliable size
- WHEN `download_file` downloads the content
- THEN the tool SHALL validate `len(content)` after download
- AND reject content larger than the configured maximum allowed file size

#### Scenario: Upload validates size before writing

- GIVEN a Dify file upload
- WHEN `upload_file` is invoked
- THEN the tool SHALL validate the size before uploading to Daytona
- AND SHALL avoid unnecessary repeated blob reads where possible

### Requirement: Safer Git clone verification

The `git_clone` tool SHALL verify successful clones using Git status when available and SHALL never return credentials.

#### Scenario: Clone and return branch status

- GIVEN an existing sandbox and a public Git repository URL
- WHEN `git_clone` clones the repository into a target path
- THEN the tool SHALL attempt to read Git status from the target path
- AND return `current_branch` when available
- AND return `status: cloned`

#### Scenario: Git status unavailable after clone

- GIVEN Git status verification fails after a clone operation
- WHEN filesystem listing of the target path succeeds
- THEN the tool SHALL still return `status: cloned`
- AND include safe filesystem verification metadata

#### Scenario: Private repository credentials are used

- GIVEN username and password or token are provided for a private repository
- WHEN `git_clone` invokes the Daytona SDK clone operation
- THEN the tool SHALL pass credentials directly to the SDK
- AND SHALL not include username, password, or token values in returned JSON or text output

### Requirement: Explicit ephemeral one-off execution

One-off execution tools SHALL create implicit sandboxes with explicit ephemeral lifecycle settings where supported by the SDK.

#### Scenario: Run code without sandbox ID

- GIVEN `run_code` is invoked without `sandbox_id`
- WHEN the plugin creates a sandbox implicitly
- THEN it SHALL request an ephemeral sandbox with a short auto-stop interval
- AND SHALL delete the sandbox in a cleanup block after execution

#### Scenario: Run command without sandbox ID

- GIVEN `run_command` is invoked without `sandbox_id`
- WHEN the plugin creates a sandbox implicitly
- THEN it SHALL request an ephemeral sandbox with a short auto-stop interval
- AND SHALL delete the sandbox in a cleanup block after execution

### Requirement: Selected sandbox creation controls

The `create_sandbox` tool SHALL expose selected official Daytona SDK sandbox creation controls that are useful for Dify agent workflows.

#### Scenario: Create sandbox with labels

- GIVEN `create_sandbox` receives `labels` as a JSON object string
- WHEN the sandbox is created
- THEN the plugin SHALL pass labels to the Daytona SDK as a string dictionary

#### Scenario: Create sandbox with network restrictions

- GIVEN `create_sandbox` receives `network_block_all` or `network_allow_list`
- WHEN the sandbox is created
- THEN the plugin SHALL pass the requested network controls to the Daytona SDK

#### Scenario: Create public sandbox

- GIVEN `create_sandbox` receives `public: true`
- WHEN the sandbox is created
- THEN the plugin SHALL pass the public sandbox option to the Daytona SDK

## MODIFIED Requirements

### Requirement: Accurate command execution output contract

The `run_command` tool SHALL document and return Daytona's combined command output and exit code, not separate stdout and stderr fields unless the SDK provides them directly for that execution path.

#### Scenario: Command produces output

- GIVEN an existing sandbox
- WHEN `run_command` runs a shell command
- THEN the tool SHALL return `exit_code`, `output`, and `sandbox_id`
- AND documentation SHALL describe `output` as combined output

### Requirement: Preview URL token handling

The `get_preview_url` tool SHALL avoid exposing preview tokens to the LLM by default.

#### Scenario: Get preview URL with default parameters

- GIVEN an existing sandbox running a service on a supported port
- WHEN `get_preview_url` is invoked without an explicit token opt-in
- THEN the tool SHALL return the preview URL, port, and sandbox ID
- AND SHALL not return the raw preview token in the default JSON output

#### Scenario: Explicit token opt-in

- GIVEN a caller explicitly requests token details if the tool supports this option
- WHEN `get_preview_url` returns token metadata
- THEN the tool SHALL make token exposure explicit in the tool contract
- AND documentation SHALL explain that private previews require the token header

### Requirement: Reproducible packaging dependencies

The plugin package SHALL declare dependency constraints that match the SDK versions validated by the implementation.

#### Scenario: Fresh plugin install resolves dependencies

- GIVEN the plugin is installed in a clean Dify plugin runtime
- WHEN dependencies are resolved from `requirements.txt`
- THEN the resolved Daytona SDK version SHALL be within the tested compatibility range
- AND provider and tool imports SHALL succeed

### Requirement: Current documentation

The README SHALL describe all released tools and their actual parameters and return values.

#### Scenario: User reads tool reference

- GIVEN a user opens the README for the plugin release
- WHEN the user reviews the tool reference
- THEN every registered tool SHALL be listed
- AND each tool's documented return fields SHALL match implementation behavior
