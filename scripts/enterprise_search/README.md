# Main Agent search PoC

This pilot uses the real `chat_service.handle_chat` → `AgentExecutor` →
`ReactAgent` path and the configured model. It does not replace the model or
hard-code its tool choices. It does not install the Skill into a user's remote
library or change the running application's frontend/Core configuration.

## Run

Use the existing algorithm Python environment and service configuration. The
Spotlight host uses only Python's standard library and must run on macOS:

```sh
python scripts/enterprise_search/spotlight_host.py
```

Before starting, supply `LAZYMIND_SPOTLIGHT_TOKEN` with a random secret of at
least 32 characters. The default bind is `127.0.0.1:19093`. If Chat is in a
container, explicitly bind an interface it can reach with `--bind`; stop this
temporary server when the pilot finishes. Only authenticated `POST /search`
requests are accepted. The server cannot open files or execute arbitrary shell
commands. Home scope is derived by the Mac process, never supplied by the model.

Configure the separate Chat pilot process:

- `LAZYMIND_SPOTLIGHT_URL`: the reachable host's `/search` URL.
- `LAZYMIND_SPOTLIGHT_TOKEN`: the same secret, never checked into the repository.
- `LAZYMIND_SPOTLIGHT_USER_ID`: the one LazyMind user allowed to use this host.
- `LAZYMIND_SKILL_FS_URL`: this checkout's absolute `skills/search` directory.
- `LAZYMIND_MODEL_CONFIG_PATH`: the existing usable model configuration.
- `PYTHONPATH`: this checkout's `algorithm` and `algorithm/lazyllm` directories.

From a working directory that does not shadow this checkout's imports:

```sh
python /path/to/checkout/scripts/enterprise_search/run_agent_poc.py \
  --case code --user-id USER_ID \
  --scope /already/authorized/project \
  --output /private/results/code.json
```

Available cases: `code`, `ppt`, `feishu`, `xlsx-gap`. `--scope` supplies the
existing **read authorization**, not a path in the user's question. These
authorized source roots may be visible in the normal Agent runtime context;
this is not a blind directory-discovery benchmark. Omit scopes for discovery
without read access. The Spotlight query defaults to the home directory, and
the model can narrow to a discovered or already-authorized directory.

For Feishu, pass `--mcp-config /private/feishu.json`, containing the existing
runtime MCP server list: `name`, `url`, `transport`, `headers`, `allowed_tools`.
Obtain the current user credential through LazyMind's existing OAuth service;
do not copy a credential into the Skill. Restrict allowed tools to `search-doc`
and `fetch-doc`. This pilot accepts a current credential snapshot; it does not
implement automatic OAuth renewal. Notion can use the same runtime MCP path
when a LazyMind-owned content-search connection is available; a Codex connector
is not such a connection.

## Inspect results

The JSON includes the question, scopes, elapsed time and original Chat stream.
An adjacent `.events.jsonl` is flushed as events arrive. Inspect the actual
`get_skill`, search, read and final answer events; a completed turn or successful
tool status alone is not a passing answer. Preserve failed calls and coverage
gaps, and check cited paths/URLs against tool outputs. Files containing results
are private by default.

If a model transport failure interrupts a run, a separately labeled retry can
use `--resume-events /private/results/feishu.events.jsonl`. This replays the
original product-format Chat history and validates that complete tool exchanges
survive normalization. Keep the failed run and report the retry separately;
do not count a recovered answer as first-attempt success. A longer model timeout
can be set in a private pilot config without changing the application's model.

Local text and Office reads reuse the existing authorized readers. The current
generic document reader accepts PPTX but the pilot's configured parsing route
failed to read it; XLSX is not accepted. The Excel case evaluates
native **discovery** and honest empty-result reporting. It does not establish
Excel reading support. No rg route, persistent index, batch extraction fallback,
ranking optimization or frontend development is included.

The pilot disables the existing `local_fs` toolkit because it also exposes
project-wide grep. Reading authorized files uses the existing `read_file`
entrypoint instead; the ordinary application's local tools remain unchanged.

## Abstraction boundary

Spotlight stays an OS-specific adapter; there is only one implementation, so no
new search base class is introduced. Local read permissions reuse
`LocalFileToolkit` and Office parsing reuses the existing resource resolver.
The observed MCP SDK 1/2 compatibility fixes belong in the shared LazyLLM
MCP client/adapter, so cloud providers share the same corrected behavior.
