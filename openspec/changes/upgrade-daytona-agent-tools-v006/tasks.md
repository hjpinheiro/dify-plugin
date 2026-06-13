# Tasks

## 1. SDK Compatibility and Dependencies

- [ ] 1.1 Fix provider credential validation to call `daytona.list(ListSandboxesQuery(limit=1))`.
- [ ] 1.2 Decide and update the Daytona dependency constraint to the tested SDK family, preferably `daytona>=0.187.0,<0.188.0`.
- [ ] 1.3 Reconcile `requirements.txt`, `pyproject.toml`, and `uv.lock` so they describe the same supported dependency set.
- [ ] 1.4 Run import validation for provider and all tools.

## 2. File Reading and Writing Tools

- [ ] 2.1 Add `tools/read_file.py` with size checks, UTF-8 decoding, `max_bytes`, and `truncated` metadata.
- [ ] 2.2 Add `tools/read_file.yaml` with LLM-friendly descriptions and safe defaults.
- [ ] 2.3 Add `tools/write_file.py` using `sandbox.fs.upload_file` for text content with `MAX_FILE_SIZE` enforcement.
- [ ] 2.4 Add `tools/write_file.yaml` with required `sandbox_id`, `remote_path`, and `content` parameters.
- [ ] 2.5 Register both tools in `provider/daytona.yaml`.

## 3. Bounded Filesystem Outputs

- [ ] 3.1 Add `max_results` and `truncated` handling to `list_files`.
- [ ] 3.2 Add `max_results` and `truncated` handling to `search_files`.
- [ ] 3.3 Clamp `find_in_files.max_results` to a safe range, e.g. `1..200`.
- [ ] 3.4 Ensure text summaries clearly mention truncation when it occurs.

## 4. File Transfer Hardening

- [ ] 4.1 Add post-download `len(content)` size validation in `download_file`.
- [ ] 4.2 Avoid repeated `file.blob` reads in `upload_file`; cache the blob after size validation when needed.
- [ ] 4.3 Preserve existing blob message behavior for downloadable artifacts.

## 5. Git Clone Improvements

- [ ] 5.1 Move `git_clone.password` from LLM-generated input to a runtime/form secret input.
- [ ] 5.2 Add `sandbox.git.status(path)` verification after clone.
- [ ] 5.3 Return `current_branch` and safe status metadata when available.
- [ ] 5.4 Keep filesystem listing fallback if Git status verification fails.
- [ ] 5.5 Confirm no username/password/token value appears in JSON or text output.

## 6. Preview URL Token Handling

- [ ] 6.1 Decide whether to omit preview token by default or gate it behind `include_token`.
- [ ] 6.2 Update `get_preview_url.py` and YAML accordingly.
- [ ] 6.3 Update README to describe private preview behavior accurately.

## 7. Ephemeral Sandbox and Creation Controls

- [ ] 7.1 Update implicit `run_code` sandbox creation to use explicit ephemeral settings.
- [ ] 7.2 Update implicit `run_command` sandbox creation to use explicit ephemeral settings.
- [ ] 7.3 Add selected `create_sandbox` parameters: `public`, `labels`, `network_block_all`, `network_allow_list`, `auto_delete_interval`, `auto_archive_interval`, `ephemeral`.
- [ ] 7.4 Parse and validate `labels` as a JSON object string.
- [ ] 7.5 Avoid changing existing default behavior unless explicitly documented.

## 8. Documentation and Packaging

- [ ] 8.1 Bump `manifest.yaml` and provider metadata to `0.0.6`.
- [ ] 8.2 Update README feature list and tool reference to include all tools and correct outputs.
- [ ] 8.3 Update README source link to the active fork if this package is released from `hjpinheiro/dify-plugin`.
- [ ] 8.4 Generate `daytona.difypkg` using `package.py`.
- [ ] 8.5 Verify the package contains files only, no directory entries, and includes new YAML/Python files.

## 9. Verification

- [ ] 9.1 Run Python syntax/import checks for provider and tool modules.
- [ ] 9.2 Run package generation.
- [ ] 9.3 If Daytona credentials are available, smoke-test provider validation.
- [ ] 9.4 If Dify is available, install the generated package and confirm the tool list.
- [ ] 9.5 Smoke-test an agent workflow: create sandbox, clone repo, list files, read file, write file, run command, destroy sandbox.
