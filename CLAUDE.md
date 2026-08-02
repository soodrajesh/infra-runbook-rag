# CLAUDE.md

## Project type
Python CLI (click), RAG over markdown docs. See README.md for architecture.

## Commands
- Install: `pip install -r requirements.txt`
- Run: `python -m rag.cli ingest <repo-path>` then `python -m rag.cli ask "<question>"`
- Test: `pytest`

## Notes
- Embeddings are local (sentence-transformers); generation calls the OpenAI API (`gpt-4o-mini`)
  and needs `OPENAI_API_KEY` set.
- Tests must not require a real API key or model download — mock `openai` clients and
  `rag.embed.embed` as done in `tests/test_ask.py`.
