# Native search POC

Current product tools:

- `LocalFileToolkit.search`: macOS Spotlight / Windows Search; default OS-index scope.
- Feishu supplier `search_documents`: one page of ordinary documents + Wiki, using existing user OAuth.
- `enterprise-search`: source selection, query reformulation, evidence-driven reading.

No workspace/permission changes, indexing, document ingestion, or deployment is needed for discovery.
The other LocalFileToolkit methods retain their existing directory permissions.

## Run the tool POC

Use the project's Python runtime with `algorithm` and `algorithm/lazyllm` on PYTHONPATH.
From the repository root on macOS:

```sh
PYTHONPATH=algorithm:algorithm/lazyllm python scripts/enterprise_search/native_search_poc.py local LazyMind --match name
PYTHONPATH=algorithm:algorithm/lazyllm python scripts/enterprise_search/native_search_poc.py local LocalFileToolkit --match content --path /your/project
```

On Windows PowerShell:

```powershell
$env:PYTHONPATH = 'algorithm;algorithm/lazyllm'
python scripts/enterprise_search/native_search_poc.py local LazyMind --match name
```

The fixed Windows helper queries the read-only Search.CollatorDSO provider through
Windows PowerShell. Only its fixed source is encoded into the command; request
values travel over stdin. Windows Search must be available and the documents
indexed. No indexing service is started or configured by the tool.

For Feishu, provide an existing connected user's access token through
`FEISHU_USER_ACCESS_TOKEN`, then run:

```sh
PYTHONPATH=algorithm:algorithm/lazyllm python scripts/enterprise_search/native_search_poc.py feishu LazyMind
```

Do not put the token in command arguments or source files. This direct tool smoke
runner does not refresh credentials. The normal product continues to use its
existing OAuth lifecycle. Results can contain private document metadata; save
outputs only in a private location when necessary.

## Current validation (2026-09-11)

- Actual macOS name/directory search and scoped body search succeeded; result limits reported as partial.
- Local permissions, tool registration, Feishu paging and user-token injection have automated coverage.
- Windows implementation is not yet validated on a real Windows machine.
- The 8091 POC user had no chat-enabled Feishu connection. At the user's request,
  the existing active 8090 user OAuth connection was used for read-only verification.
- Real global search: LazyMind returned 1 Wiki result; 工作 returned 197 matches
  with ordinary cloud documents; 方案 returned 129 matches with both DOC and WIKI.
  Counts are a point-in-time provider response, not a recall measurement.
- The returned Wiki URL was read successfully through existing read_with_references;
  the returned text contained LazyMind. Ordinary-document reading was not separately checked.
- Important API detail: both doc_filter={} and wiki_filter={} must be sent. Omitting
  them produced a successful zero-hit response; including them returned the matches above.
  Page size is capped at 20, matching the official Lark CLI.
- The 8090 configuration and services were not modified/restarted; credentials were
  obtained through its existing OAuth token endpoint and were not written to files.
- Full Agent + Skill behavior and Office/OCR coverage remain unverified in this revision.
- No service restart/deployment, bulk parsing or reindexing performed.

`run_agent_poc.py` and `README.md` describe the earlier bridge/MCP experiment;
its tool filtering targets the removed independent Spotlight registration. Use
this runner for the current tool POC, not the legacy runner. The legacy HTTP host
remains home-scoped and is not registered in the product.
