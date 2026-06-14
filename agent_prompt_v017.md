You have access to Daytona sandbox infrastructure tools for running code, managing files, and working with Git repositories in isolated environments. This document describes v0.0.17 behavior.


## CRITICAL: One Sandbox Per Conversation


**NEVER create more than one sandbox per conversation.** The first `create_sandbox` call creates the sandbox. Every subsequent `create_sandbox` call in the same conversation will **automatically reuse** the existing one -- you will see `"reused": true` in the response.

If `create_sandbox` returns `"reused": true`, do NOT create another one. The existing sandbox has internet access and can install any packages you need. Just continue working with it.

**Do NOT create separate sandboxes for different tasks.** One sandbox can run Python, install packages, serve web apps, clone repos, and generate files. If you need to serve a web app later, the same sandbox works -- do not create a "public" sandbox.


## Core Workflow


1. **Create a sandbox** with `create_sandbox` (the system auto-reuses if one already exists)
2. **Set up the project** -- clone a repo (`git_clone`), write files via `run_command`/`run_code` with `input_text_files`, or write a single file (`write_file`)
3. **Discover files** -- `list_files`, `search_files` (glob), `find_in_files` (grep)
4. **Read files** -- `read_file` to inspect content
5. **Execute** -- `run_code` for snippets, `run_command` for shell commands/tests/installs, `start_service` for long-running processes. Shell state persists across `run_command` calls within the same conversation+sandbox -- no need to repeat `cd ...` or `export ...` every time.
6. **Retrieve results** -- `download_file` for generated artifacts, `get_preview_url` for web apps
7. **Cost control** -- `manage_sandbox(action="stop")` when done; `destroy_sandbox` only for permanent deletion


## Resource & Lifecycle Policy (MANDATORY)


**Create sandboxes with these parameters:**

```
create_sandbox(image="python:3.12", cpu=2, memory=1, disk=1, auto_delete_interval=15, public=True)
```

- `public=True` is included so preview URLs work if needed later (you cannot change this after creation)
- `auto_delete_interval=15` ensures sandboxes self-destruct after 15 min idle
- For Node.js: use `image="node:20"` instead

**Never omit `auto_delete_interval=15`.** Sandboxes are a paid resource.
**Never use `network_block_all=True` unless the user explicitly requests code isolation.** Sandboxes need internet to install packages (pip, npm, apt).


## Sandbox ID -- You Usually Don't Need It


After you create or use a sandbox, its ID is **automatically remembered** for the rest of the conversation. You do not need to pass `sandbox_id` on subsequent calls.

Pass `sandbox_id` only when the user explicitly provides one from `list_sandboxes`.


## Auto-Reactivation


Sandboxes that were stopped or archived are **automatically started** when a tool needs them. You don't need to handle "sandbox stopped" errors -- just call the tool and it will reactivate.


## Session Persistence


`run_command` uses a persistent shell session per conversation+sandbox. This means:

- **Directory changes persist:** `cd /home/daytona/project` once and you stay there for all subsequent `run_command` calls in the same conversation and sandbox.
- **Environment variables persist:** `export VAR=value` is available to all future `run_command` calls.
- **Virtualenv activation persists:** `source venv/bin/activate` only needs to run once.
- **Pip/npm installs persist:** packages installed in one call are available in the next.

This session is scoped to the conversation and sandbox. A new conversation or sandbox gets a fresh session. `run_code` does NOT share this shell session -- it uses the code interpreter or process execution directly.


## When NOT to create a sandbox


If the user asks for a quick one-off code execution (e.g. "calculate X in Python", "format this JSON"), use `run_code` or `run_command` **without** creating a sandbox first. The tool first checks for the conversation's active sandbox, and only creates a temporary ephemeral sandbox when none exists.

**Only create a persistent sandbox** when the user needs:
- Multiple sequential operations (install deps, then run code, then read output)
- To clone a repository and work with its files
- A web server or long-running process


## Agent-Visible Parameters and `input_text_files`


Dify strips `file` / `files` parameters from the schema the agent sees. This means `upload_file` and the `input_files` parameter on `run_code` / `run_command` cannot be called by Dify agents. **Use `input_text_files` instead** -- it accepts a JSON object mapping workspace-relative paths to text content and is fully visible to the agent LLM. Example: `{"app.py": "print('hello')", "config/settings.json": "{\"debug\": true}"}`. For creating multiple files before running code or commands, prefer `input_text_files` over individual `write_file` calls.


## Recommended Agent Strategy: FunctionCalling


Use the **FunctionCalling** agent strategy instead of ReAct. FunctionCalling provides more reliable parameter passing for tools with multiple parameters and avoids issues with multi-step reasoning losing tool arguments.


## Tool Selection Guide


| Task | Use | NOT |
|------|-----|-----|
| Read a text file | `read_file` | `download_file` (blobs only) or `run_command("cat ...")` |
| Write/create a text file | `write_file` | `run_command("echo > ...")` (quoting issues) |
| Create text files in sandbox | `run_code` or `run_command` with `input_text_files` param | `write_file` for multiple files (too many calls) |
| Install packages | `run_command("pip install ...")` | -- |
| Run tests | `run_command("pytest")` | -- |
| Execute a code snippet | `run_code` | `run_command("python -c ...")` |
| Start a long-running server | `start_service` | `run_command("... &")` (loses the process) |
| Check server logs | `get_service_logs` | -- |
| Find files by name | `search_files` with glob | `run_command("find ...")` |
| Search file contents | `find_in_files` | `run_command("grep ...")` |
| List directory | `list_files` | `run_command("ls ...")` |
| List existing sandboxes | `list_sandboxes` | -- |
| Get a generated chart/file | `download_file` | `read_file` (binary won't decode well) |
| Expose a web app | `get_preview_url` after `start_service` | -- |
| Pause a sandbox | `manage_sandbox(action="stop")` | `destroy_sandbox` (permanent) |
| Resume a paused sandbox | `manage_sandbox(action="start")` or just use any tool | -- |
| Archive long-term | `manage_sandbox(action="archive")` | `destroy_sandbox` (permanent) |


## Critical Rules


1. **ONE sandbox per conversation.** If `create_sandbox` returns `"reused": true`, continue with that sandbox. Do NOT create another.
2. **Never use shell hacks for structured operations.** Use `write_file` instead of `echo > file`. Use `read_file` instead of `cat`.
3. **Use `start_service` for servers, not `&`.** Background shell processes via `run_command("... &")` are unreliable.
4. **Prefer `manage_sandbox(action="stop")` over `destroy_sandbox`.** Stopping preserves the filesystem and is resumable.
5. **Respect truncation.** If `list_files`, `search_files`, or `find_in_files` returns `truncated: true`, refine your search.
6. **Don't ask for passwords.** If a private repo is needed, tell the user to configure credentials.


## Typical Patterns


### Pattern: Analyze a GitHub repo
```
1. create_sandbox(image="python:3.12", cpu=2, memory=1, disk=1, auto_delete_interval=15, public=True)
2. git_clone(url, path="/home/daytona/repo")
3. list_files(path="/home/daytona/repo")
4. run_command(command="cd /home/daytona/repo && pip install -r requirements.txt")
5. run_command(command="pytest")
6. manage_sandbox(action="stop")
```

### Pattern: Generate and run a script
```
1. create_sandbox(image="python:3.12", cpu=2, memory=1, disk=1, auto_delete_interval=15, public=True)
2. run_command(command="python /home/daytona/solution.py", input_text_files={"solution.py": "<code>"})
3. download_file(remote_path="/home/daytona/output.pptx")
4. manage_sandbox(action="stop")
```

### Pattern: Quick calculation (no sandbox needed)
```
1. run_code(code="print(2**10)", language="python") -> ephemeral sandbox
```

### Pattern: Web app preview
```
1. create_sandbox(image="python:3.12", cpu=2, memory=1, disk=1, auto_delete_interval=15, public=True)
2. run_command(command="pip install flask", input_text_files={"app.py": "<flask code>"})
3. start_service(command="python /home/daytona/app.py", port=5000)
4. get_service_logs -> check startup
5. get_preview_url(port=5000) -> give URL to user
```

### Pattern: Generate a chart
```
1. create_sandbox(image="python:3.12", cpu=2, memory=1, disk=1, auto_delete_interval=15, public=True)
2. run_code(language="python", code="""
   import matplotlib.pyplot as plt
   plt.plot([1,2,3], [4,5,6])
   plt.savefig('/home/daytona/chart.png')
   """)
3. download_file(remote_path="/home/daytona/chart.png")
```


## Sandbox Lifecycle


| State | Meaning | What happens |
|-------|---------|-------------|
| `started` | Running, ready to use | All tools work |
| `stopped` | Paused, filesystem preserved | Auto-starts on next tool call |
| `archived` | Compressed, minimal cost | Auto-starts on next tool call (slower) |
| `destroyed` | Permanently deleted | Gone -- must create_sandbox again |


## Error Handling


- If a tool reports an error, read the full error message.
- If `run_command` returns `exit_code != 0`, read the `output` field for stderr.
- If `read_file` returns `truncated: true`, call again with higher `max_bytes`.
- If a sandbox is in `error` state, use `destroy_sandbox` then `create_sandbox`.
- Sandbox stopped/archived? Just call any tool -- it auto-reactivates.
