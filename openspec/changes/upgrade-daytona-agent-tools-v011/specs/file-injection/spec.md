## ADDED Requirements

### Requirement: Direct file injection into execution

The provider SHALL accept optional `input_files` on `run_code` and
`run_command` that are automatically uploaded to the sandbox workspace before
execution, eliminating the need for a separate `upload_file` step.

#### Scenario: Single file injection

- GIVEN an agent calls `run_code` with `input_files` containing one CSV file
- WHEN the tool executes
- THEN the file SHALL be uploaded to `/home/daytona/workspace/{filename}`
  before code runs
- AND the JSON response SHALL include `uploaded_files` listing the paths

#### Scenario: No file injection (backward compat)

- GIVEN `run_code` is called without `input_files`
- WHEN the tool executes
- THEN no upload step SHALL occur
- AND behavior SHALL be identical to the previous version

#### Scenario: File size validation

- GIVEN an `input_files` entry exceeds `MAX_FILE_SIZE` (100 MB)
- WHEN the tool validates before upload
- THEN the tool SHALL raise a clear error
- AND SHALL NOT attempt the upload

#### Scenario: Multiple files

- GIVEN `input_files` contains multiple files
- WHEN the tool executes
- THEN all files SHALL be uploaded to the workspace directory
- AND all paths SHALL be listed in the response
