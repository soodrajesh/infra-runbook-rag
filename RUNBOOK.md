# Runbook

Step-by-step commands to set this up, ingest a repo's docs, ask questions, and run the tests.
Everything here assumes you're in the repo root (`infra-runbook-rag/`).

## 0. Prerequisites

```bash
python3 --version   # tested with 3.9
```

No other system dependencies — `sentence-transformers` and `openai` are installed into a venv
in step 1.

## 1. Set up

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Get an OpenAI API key from [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
(needs billing enabled — this calls a paid model, `gpt-4o-mini`). Then:

```bash
cp .env.example .env
# edit .env, set OPENAI_API_KEY=sk-...
export $(cat .env | xargs)
```

## 2. Ingest a repo's docs

```bash
python -m rag.cli ingest <path-to-repo> --glob "*.md"
```

Example, against this project's sibling repo:

```bash
python -m rag.cli ingest ../minikube-gitops-platform --glob "*.md"
```

First run downloads the local embedding model (`all-MiniLM-L6-v2`, ~90MB) — after that it's
offline. This walks `<path-to-repo>` for files matching `--glob` (default `*.md`), splits each on
`##`/`###` headers, embeds every section, and writes them to `rag.db` in the current directory
(override with `--db <path>`). Output looks like:

```text
Embedding 24 chunks from ../minikube-gitops-platform ...
Stored 24 chunks in rag.db
```

Re-running `ingest` against the same or a different repo replaces the store's contents —
see **Troubleshooting → Re-ingesting always replaces, never merges** below.

## 3. Ask a question

```bash
python -m rag.cli ask "<question>"
```

Example:

```bash
python -m rag.cli ask "how do I rotate or reseal the demo secret?"
```

Retrieves the top-4 most relevant chunks from `rag.db` (`-k <n>` to change that) and asks
`gpt-4o-mini` to answer using only those excerpts, citing each claim as
`[source_file § section]`. Needs `OPENAI_API_KEY` set (step 1) and a populated `rag.db`
(step 2) — both are checked up front with a clear error if missing.

## 4. Run the tests

```bash
pytest
```

Fully offline — no API key or model download needed. Embeddings and the OpenAI client are
mocked in `tests/test_ask.py`; chunking/retrieval tests use synthetic vectors.

## Troubleshooting

Edge cases found while auditing this tool, and how the code now handles them.

### Ingest

**Vendored docs pollute the corpus** — walking a repo for `*.md` will also descend into
`.venv/`, `node_modules/`, `.git/`, `__pycache__/`, `.pytest_cache/`, `dist/`, `build/` if they
exist under the target path, picking up unrelated READMEs from installed packages or cached test
artifacts. `rag/chunk.py`'s `chunk_repo` now prunes those directories during the walk
(`SKIP_DIRS`). If you hit a corpus that looks unexpectedly large, check `rag ingest` output for a
chunk count that doesn't match your intuition of "how many doc sections does this repo actually
have" — that's usually vendored content leaking in.

**Malformed markdown (unbalanced code fences)** — `chunk_markdown` toggles "inside a code block"
on every ` ``` ` line. A doc with an odd number of fences will leave the parser stuck
"inside a code block" for the rest of the file, silently swallowing any further `##` headers into
the last section's text instead of splitting on them. Not auto-fixed — if a doc's chunks look
suspiciously merged, `grep -c '```' <file>` should be even.

**Re-ingesting always replaces, never merges** — `rag ingest` calls `store.clear()` before
writing. There's no way to ingest two repos into one store; the second `ingest` wipes the first.
Intentional for now (see README's "What's missing"), not a bug.

### Ask

**`OPENAI_API_KEY` unset** — `rag ask` fails fast with a clear `ClickException` before making any
API call. If you see a raw `openai` traceback instead, you're calling `rag/ask.py`'s `answer()`
directly (e.g. from a script or REPL) rather than through the CLI, which skips that check.

**`rag.db` not found** — `rag ask` fails fast with a clear error telling you to run
`rag ingest <repo-path>` first, rather than a raw SQLite error.

**Store built with a different embedding model than the one currently installed** — `Store.add`
and `Store.top_k` now raise a clear `ValueError` ("embedding dim N doesn't match the M-dim
vectors...") instead of numpy failing on a shape mismatch deep in `np.dot`. Fix: `rag ingest`
again against the same repo to rebuild the store with the current model.

**Model returns no content** (e.g. content filtering) — `answer()` returns a plain string saying
so instead of crashing on `None`. If you see this often for legitimate questions, it's worth
checking the actual excerpts being sent — usually means the retrieved context is thin or
off-topic, not a real refusal.

**Retrieval finds a related-but-wrong section** — the known limitation from the README: header
chunking + a small local embedding model means a question about "rotating the secret" can surface
a *related* section (like install prerequisites) instead of the exact command
(`scripts/reseal-demo-secret.sh`). Confirmed live during testing — not a crash, just an accuracy
ceiling of the v1 retrieval approach. Smaller chunks or a stronger embedding model would help.

**`invalid_request_error: credit balance too low`** — the OpenAI key works but the account has no
billing/credits attached. Fix at
[platform.openai.com/settings/organization/billing](https://platform.openai.com/settings/organization/billing).

### Secrets

**`.env` / `api.env`** — both are gitignored. `*.db` is also gitignored generically (not just
`rag.db`), so custom `--db` paths from `rag ingest --db foo.db` won't accidentally get committed
either. Before ever running `git add -A` in this repo, double check `git status` doesn't list
`.env` — a gitignore miss on a real API key is the one mistake here that can't be undone by
force-pushing it away.
