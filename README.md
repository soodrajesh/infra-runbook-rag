# infra-runbook-rag

A small CLI (+ Streamlit UI) that answers on-call-style questions ("why would this 502", "how do
I rotate the sealing key") over an infra repo's own markdown docs — README, RUNBOOK, SECURITY —
with answers cited back to the exact source file and section, not just a filename.

## How it works

```
rag ingest <repo-path>          # chunk *.md by header, embed locally, store in SQLite
rag ask "<question>"            # embed the question, retrieve top-k chunks, ask the LLM
streamlit run ui.py              # same flow, in a browser, with retrieved-chunk scores visible
```

- **Chunking** (`rag/chunk.py`): splits each markdown file on `##`/`###` headers, then further
  splits any section over 600 characters into paragraph-packed sub-chunks — that's what makes
  citations like `[RUNBOOK.md § Rotate the sealing key (part 2/3)]` precise enough for a specific
  command to win retrieval instead of getting diluted by the rest of a long section.
- **Embeddings** (`rag/embed.py`): local, via `sentence-transformers` (`all-MiniLM-L6-v2`) — no
  extra API key, runs offline after the first model download.
- **Storage/retrieval** (`rag/store.py`): SQLite table of `(source_file, section, text,
  embedding)`. Retrieval is brute-force cosine similarity in numpy — no vector index, since a
  repo's worth of docs is a few dozen chunks at most.
- **Answering** (`rag/ask.py`): top-k chunks go into an OpenAI (`gpt-4o-mini`) prompt with a
  system instruction to answer only from the provided excerpts and cite the section each claim
  came from.

## Setup, usage, tests

See [RUNBOOK.md](RUNBOOK.md) for step-by-step commands: environment setup, ingesting a repo's
docs, asking questions, running the test suite, and troubleshooting (vendored docs polluting the
corpus, embedding-dimension mismatches after switching models, malformed markdown, and the
accuracy ceiling of the current retrieval approach).

## What's missing

Single-repo, CLI-only demo, not a production tool:

- No incremental ingest — re-running `ingest` truncates and rebuilds the whole store.
- No live cluster/metrics data, docs only — an obvious next step is folding in a live
  `kubectl`/Prometheus query as an additional retrieval source alongside the docs.
- No reranking — top-k is pure cosine similarity over a local MiniLM embedding. Paragraph-level
  sub-chunking (see RUNBOOK) closed the worst case of this, but it's still not a real reranker or
  a stronger embedding model (e.g. Voyage AI), which would matter more past a handful of files.
