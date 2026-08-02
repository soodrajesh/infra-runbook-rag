"""Retrieve relevant chunks and answer a question via an LLM, with citations."""

from .embed import embed
from .store import ScoredChunk, Store

MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = (
    "You are an on-call assistant answering questions about an infrastructure repo using only "
    "the provided doc excerpts. Each excerpt is labeled with its source file and section. "
    "Answer concisely, and after any claim, cite the excerpt it came from as "
    "[source_file § section]. If the excerpts don't contain the answer, say so plainly instead "
    "of guessing."
)


def format_context(chunks: list[ScoredChunk]) -> str:
    parts = []
    for c in chunks:
        parts.append(f"[{c.source_file} § {c.section}]\n{c.text}")
    return "\n\n---\n\n".join(parts)


def retrieve(store: Store, question: str, k: int = 4) -> list[ScoredChunk]:
    query_embedding = embed([question])[0]
    return store.top_k(query_embedding, k=k)


def answer(client, store: Store, question: str, k: int = 4) -> str:
    chunks = retrieve(store, question, k=k)
    if not chunks:
        return "No documents have been ingested yet — run `rag ingest <path>` first."

    context = format_context(chunks)
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Doc excerpts:\n\n{context}\n\nQuestion: {question}",
            },
        ],
    )
    return response.choices[0].message.content or "The model returned no content (this can happen with content filtering)."
