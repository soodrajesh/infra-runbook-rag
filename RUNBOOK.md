# Runbook

Operational edge cases found while auditing this tool, and how the code now handles them.

## Ingest

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

## Ask

**`OPENAI_API_KEY` unset** — `rag ask` fails fast with a clear `ClickException` before making any
API call. If you see a raw `openai` traceback instead, you're calling `rag/ask.py`'s `answer()`
directly (e.g. from a script or REPL) rather than through the CLI, which skips that check.

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

## Secrets

**`.env` / `api.env`** — both are gitignored. `*.db` is also gitignored generically (not just
`rag.db`), so custom `--db` paths from `rag ingest --db foo.db` won't accidentally get committed
either. Before ever running `git add -A` in this repo, double check `git status` doesn't list
`.env` — a gitignore miss on a real API key is the one mistake here that can't be undone by
force-pushing it away.
