## Daytona

### Description

Dify plugin for [Daytona](https://www.daytona.io/), secure sandbox infrastructure for AI agents. Create isolated sandboxes, run code, execute shell commands, manage files, clone repositories, start background services, and manage their lifecycle directly from Dify workflows and agents.

### Features

- **Create Sandbox**. Provision an isolated sandbox from a Daytona snapshot or a custom Docker image, with optional resource limits, environment variables, network controls, labels, and lifecycle policies.
- **Start Sandbox**. Start a stopped or archived sandbox, restoring its previous state with all files preserved.
- **Stop Sandbox**. Stop a running sandbox to pause execution and reduce cost. All files and state are preserved.
- **Archive Sandbox**. Archive a sandbox for long-term storage, consuming minimal resources. Restore anytime with **Start Sandbox**.
- **Run Code**. Execute a Python, TypeScript, or JavaScript snippet in a sandbox. Supports matplotlib chart extraction with metadata (type, title). For larger or multi-file scripts, upload them with **Upload File** and run them via **Run Command**.
- **Run Command**. Run a shell command in a sandbox with optional working directory and environment variables. Returns combined output (stdout merged with stderr) and exit code.
- **Start Service**. Start a long-running background process (web server, dev server, API) in a sandbox. Returns immediately and provides a session_id for log retrieval.
- **Get Service Logs**. Fetch stdout and stderr logs from a background service session.
- **Upload File**. Upload a file from Dify into a sandbox (e.g. a CSV to analyze, a script to run).
- **Download File**. Download a file from a sandbox back into Dify (e.g. a generated chart, processed data).
- **Read File**. Read the text content of a file from a sandbox, with automatic UTF-8 decoding and truncation for large files.
- **Write File**. Write text content to a file inside a sandbox without shell quoting issues.
- **List Files**. List files and directories at a path, with bounded output and truncation metadata.
- **Search Files**. Find files by name pattern (glob), with bounded output.
- **Find In Files**. Search file contents (grep-like), with clamped result limits.
- **Git Clone**. Clone a Git repository into a sandbox, with branch/commit selection and private repo auth support.
- **Get Preview URL**. Get the public URL that exposes a port from inside a sandbox so users can open a running web app, dashboard, or API in their browser.
- **List Sandboxes**. List all Daytona sandboxes in your account, with optional state filtering.
- **Destroy Sandbox**. Stop and delete a sandbox when it is no longer needed.

### Setup

1. Create a [Daytona account](https://app.daytona.io/) if you don't have one.
2. Generate an API key from the [Daytona Dashboard](https://app.daytona.io/dashboard/keys).
3. Install this plugin in Dify and authorize it with your API key.

### Usage

#### Create and use a sandbox

Use **Create Sandbox** to provision a new environment. The contents of the sandbox depend on the snapshot or image you choose; if you provide neither, Daytona's default snapshot is used. The tool returns a `sandbox_id` you can pass to subsequent **Run Code**, **Run Command**, **Read File**, **Write File**, **Git Clone**, and other tools to reuse the same environment.

When you create a sandbox, its ID is remembered for the conversation. Subsequent tool calls that need a sandbox will automatically use the active one if `sandbox_id` is omitted.

#### Quick one-off execution

If you don't pass a `sandbox_id` to **Run Code** or **Run Command**, a temporary ephemeral sandbox is created automatically (with a 5-minute auto-stop interval), used for the execution, and destroyed afterward.

#### Background services

Use **Start Service** to run long-running processes (web servers, dev servers) in the background, then use **Get Preview URL** to get a public URL. Use **Get Service Logs** to retrieve stdout and stderr output from the service session.

#### Sandbox lifecycle management

Use **Stop Sandbox** to pause a sandbox without losing data (saves cost). Use **Start Sandbox** to resume it. Use **Archive Sandbox** for long-term storage with minimal resource usage. Sandboxes that have been stopped or archived are automatically reactivated when a tool needs them.

#### Cleanup

Use **Destroy Sandbox** to permanently delete a sandbox you provisioned with **Create Sandbox**. Ephemeral sandboxes created by **Run Code** and **Run Command** are cleaned up automatically.

### Tool Reference

| Tool | Inputs | Returns |
|------|--------|---------|
| `create_sandbox` | `name`, `snapshot`, `image`, `language`, `env_vars` (JSON), `cpu`, `memory`, `disk`, `auto_stop_interval`, `public`, `labels` (JSON), `network_block_all`, `network_allow_list`, `auto_delete_interval`, `auto_archive_interval`, `ephemeral` (all optional) | `sandbox_id` |
| `run_code` | `code` (required), `language` (optional, default `python`), `sandbox_id` (optional, uses active sandbox or creates ephemeral) | `exit_code`, `output` (combined), `sandbox_id`, `charts_count`, `chart_metadata` (type, title) |
| `run_command` | `command` (required), `cwd`, `env_vars` (JSON), `sandbox_id` (all optional except command; uses active sandbox or creates ephemeral) | `exit_code`, `output` (combined stdout+stderr), `sandbox_id` |
| `start_service` | `command` (required), `sandbox_id`, `port`, `cwd`, `session_id` (all optional except command) | `session_id`, `command`, `port`, `sandbox_id` |
| `get_service_logs` | `session_id` (required), `sandbox_id`, `cmd_id`, `max_bytes` (optional, default 5000) | `stdout`, `stderr`, `truncated` |
| `start_sandbox` | `sandbox_id` (optional, uses active sandbox if omitted) | `success`, `sandbox_id` |
| `stop_sandbox` | `sandbox_id` (optional, uses active sandbox if omitted) | `success`, `sandbox_id` |
| `archive_sandbox` | `sandbox_id` (optional, uses active sandbox if omitted) | `success`, `sandbox_id` |
| `upload_file` | `sandbox_id`, `file` (Dify file picker), `remote_path` (all required) | `success`, `sandbox_id`, `remote_path`, `size_bytes` |
| `download_file` | `sandbox_id`, `remote_path` (both required) | File as Dify blob plus `success`, `sandbox_id`, `remote_path`, `size_bytes`, `mime_type`, `filename` |
| `read_file` | `sandbox_id`, `remote_path` (required), `max_bytes` (optional, default 50 KB) | `content`, `size_bytes`, `encoding`, `truncated` |
| `write_file` | `sandbox_id`, `remote_path`, `content` (all required) | `success`, `sandbox_id`, `remote_path`, `size_bytes` |
| `list_files` | `sandbox_id`, `path` (required), `max_results` (optional, default 50, max 200) | `files[]`, `count`, `total`, `truncated`, `dirs`, `files_count` |
| `search_files` | `sandbox_id`, `path`, `pattern` (required), `max_results` (optional, default 50, max 200) | `files[]`, `count`, `total`, `truncated` |
| `find_in_files` | `sandbox_id`, `path`, `pattern` (required), `max_results` (optional, default 50, max 200) | `matches[]`, `count`, `total`, `truncated`, `files_with_matches` |
| `git_clone` | `sandbox_id`, `url`, `path` (required), `branch`, `commit_id`, `username` (optional), `password` (form input, not LLM-generated) | `status`, `current_branch`, `url`, `path` |
| `get_preview_url` | `sandbox_id`, `port` (3000–9999) (required), `include_token` (optional, default false) | `url`, `port`, `sandbox_id`, `token` (only if `include_token=true`) or `requires_token` |
| `list_sandboxes` | `limit` (optional, 1–100, default 20), `state` (optional) | `sandboxes[]`, `count`, `by_state` |
| `destroy_sandbox` | `sandbox_id` (required) | `success`, `sandbox_id` |

### Support

For questions, issues, or feedback about this plugin, contact [support@daytona.io](mailto:support@daytona.io).

### Links

- [Plugin Source Code](https://github.com/hjpinheiro/dify-plugin)
- [Daytona Documentation](https://www.daytona.io/docs)
- [Daytona Dashboard](https://app.daytona.io/)
