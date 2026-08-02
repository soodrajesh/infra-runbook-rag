"""SQLite-backed chunk store with brute-force cosine-similarity retrieval."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .chunk import Chunk

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    section TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding BLOB NOT NULL
);
"""


@dataclass
class ScoredChunk:
    source_file: str
    section: str
    text: str
    score: float


class Store:
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(SCHEMA)
        self.conn.commit()

    def clear(self) -> None:
        self.conn.execute("DELETE FROM chunks")
        self.conn.commit()

    def add(self, chunks: list[Chunk], embeddings: np.ndarray) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError(f"got {len(chunks)} chunks but {len(embeddings)} embeddings")

        existing_dim = self._embedding_dim()
        if existing_dim is not None and embeddings.shape[1] != existing_dim:
            raise ValueError(
                f"embedding dim {embeddings.shape[1]} doesn't match the {existing_dim}-dim "
                "vectors already in this store — call clear() first if you're switching "
                "embedding models"
            )

        rows = [
            (c.source_file, c.section, c.text, emb.astype("float32").tobytes())
            for c, emb in zip(chunks, embeddings)
        ]
        self.conn.executemany(
            "INSERT INTO chunks (source_file, section, text, embedding) VALUES (?, ?, ?, ?)",
            rows,
        )
        self.conn.commit()

    def _embedding_dim(self) -> int | None:
        row = self.conn.execute("SELECT embedding FROM chunks LIMIT 1").fetchone()
        if row is None:
            return None
        return len(np.frombuffer(row[0], dtype="float32"))

    def _all(self) -> list[tuple[str, str, str, np.ndarray]]:
        rows = self.conn.execute("SELECT source_file, section, text, embedding FROM chunks").fetchall()
        return [(sf, sec, text, np.frombuffer(blob, dtype="float32")) for sf, sec, text, blob in rows]

    def top_k(self, query_embedding: np.ndarray, k: int = 4) -> list[ScoredChunk]:
        rows = self._all()
        if not rows:
            return []
        stored_dim = rows[0][3].shape[0]
        if query_embedding.shape[0] != stored_dim:
            raise ValueError(
                f"query embedding dim {query_embedding.shape[0]} doesn't match the "
                f"{stored_dim}-dim vectors in this store — was it ingested with a different "
                "embedding model?"
            )
        scored = [
            ScoredChunk(source_file=sf, section=sec, text=text, score=float(np.dot(query_embedding, emb)))
            for sf, sec, text, emb in rows
        ]
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:k]

    def close(self) -> None:
        self.conn.close()
