---
name: enterprise-search
description: Locate documents and answer questions across local macOS or Windows files and connected Feishu documents and Wiki. Use for finding project information, investigating decisions, and comparing sources.
---

# Enterprise search

Use each source's native search to acquire candidates and evidence, then deepen
only where the question needs it. No global index or embedding pipeline is required.

## Choose the source and query

Inspect available tools and their schemas. Extract distinctive entities, names,
exact symbols, dates and source constraints from the question. Translate these
into short source-specific queries; do not send the whole question as keywords.

- **Local unknown location:** `LocalFileToolkit.search` uses Spotlight on macOS
  or Windows Search on Windows. Select name, content or either. Omit `path` to
  use the system index; supply a directory to narrow. Matching and index coverage
  differ by OS. It discovers paths and metadata, not document body excerpts.
- **Known names or code symbols:** use available glob/grep in an authorized,
  useful scope; native search can first locate the project. Avoid whole-disk grep.
- **Known files:** use existing `read_file` / `grep` resource tools or
  `LocalFileToolkit.read` for permitted text files. Office/PDF content uses the
  existing attachment/document parser, not a new conversion pipeline.
- **Feishu unknown location:** expand CloudFileToolkit and its Feishu supplier,
  then use `search_documents` for ordinary cloud documents and Wiki together.
  The existing `search` method searches Wiki only; it is not global coverage.
- **Scoped Wiki:** use existing Wiki search with its actual space/node parameters.
- **Feishu URL:** use the supplier's resolve/read methods directly. Preserve
  the URL; a Wiki node token is not a space id. Do not use public-web URL fetching.

Search relevant independent sources in parallel when useful. Do not query every
source mechanically if the user named one. A disconnected source or a failed
request must not prevent answering from another source's evidence.

## Decide how far to retrieve

Choose candidate counts and pagination according to the task. Continue Feishu
pagination with the returned token and the same query only if more coverage is
needed. Rank by relevance, authority, date and evidence completeness; numeric
scores from different systems are not comparable.

Metadata can answer a file-location request. A source-provided summary can support
a fact when it explicitly and sufficiently answers the question. A local body
match without an excerpt does not disclose the answer. Read relevant content
when evidence is missing, ambiguous, truncated, contradictory, or the task needs
cross-document understanding. Do not require Read on every hit or use a fixed Top K.

If results are weak, try a shorter phrase, alias, language variant or a narrower
relevant scope. Stop when the question is supported, or explain the remaining gap.
Do not initiate full-disk crawling, mass parsing, OCR or index rebuilds.

## Permissions and coverage

Native discovery does not grant read/write permission. Use existing readers;
if they deny a path, report the authorization requirement without bypassing it
through shell, another tool, or a guessed workspace permission.

Reuse the connected Feishu user's authorization. Report missing permissions,
expired authorization, unavailable search services and timeouts distinctly from
successful empty searches. Indexing may omit content or file types, especially
scans; finding a filename does not establish OCR or document-reading support.

## Answer with evidence

Provide the supported answer with returned local paths or cloud URLs beside the
claims. Cite actual line/page/slide/cell locations only when a reader supplies them.
Feishu results retain provider metadata and highlighted summaries; inspect those
fields rather than inventing URLs or assuming every result has a snippet.

Group duplicate information while retaining materially conflicting versions,
dates and sources. Distinguish design intent from observed implementation and
note material coverage gaps without claiming an exhaustive search.

Strategy adapted from Anthropic's [Search Skill](https://github.com/anthropics/knowledge-work-plugins/blob/main/enterprise-search/skills/search/SKILL.md).
