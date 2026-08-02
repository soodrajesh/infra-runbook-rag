from pathlib import Path

import numpy as np
import pytest

from rag.chunk import Chunk
from rag.store import Store


def test_top_k_ranks_by_cosine_similarity(tmp_path: Path):
    store = Store(tmp_path / "test.db")

    chunks = [
        Chunk(source_file="RUNBOOK.md", section="Rotate key", text="rotate the sealing key"),
        Chunk(source_file="RUNBOOK.md", section="502s", text="networkpolicy blocks traffic"),
        Chunk(source_file="README.md", section="Overview", text="architecture overview"),
    ]
    # Orthonormal-ish synthetic embeddings so similarity ranking is deterministic
    # without needing the real sentence-transformers model in tests.
    embeddings = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype="float32",
    )
    store.add(chunks, embeddings)

    query = np.array([0.0, 0.9, 0.1], dtype="float32")
    results = store.top_k(query, k=2)

    assert len(results) == 2
    assert results[0].section == "502s"
    assert results[0].source_file == "RUNBOOK.md"
    assert results[0].score > results[1].score

    store.close()


def test_top_k_empty_store_returns_empty(tmp_path: Path):
    store = Store(tmp_path / "empty.db")
    results = store.top_k(np.zeros(3, dtype="float32"), k=4)
    assert results == []
    store.close()


def test_add_rejects_mismatched_embedding_dim(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    store.add([Chunk(source_file="a.md", section="A", text="a")], np.array([[1.0, 0.0]], dtype="float32"))

    with pytest.raises(ValueError, match="doesn't match"):
        store.add(
            [Chunk(source_file="b.md", section="B", text="b")],
            np.array([[1.0, 0.0, 0.0]], dtype="float32"),
        )

    store.close()


def test_add_rejects_chunk_embedding_count_mismatch(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    with pytest.raises(ValueError, match="chunks but"):
        store.add(
            [Chunk(source_file="a.md", section="A", text="a"), Chunk(source_file="b.md", section="B", text="b")],
            np.array([[1.0, 0.0]], dtype="float32"),
        )
    store.close()


def test_top_k_rejects_query_with_wrong_dim(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    store.add([Chunk(source_file="a.md", section="A", text="a")], np.array([[1.0, 0.0]], dtype="float32"))

    with pytest.raises(ValueError, match="doesn't match"):
        store.top_k(np.array([1.0, 0.0, 0.0], dtype="float32"))

    store.close()


def test_clear_removes_existing_chunks(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    chunks = [Chunk(source_file="a.md", section="A", text="a")]
    embeddings = np.array([[1.0, 0.0]], dtype="float32")
    store.add(chunks, embeddings)
    store.clear()

    results = store.top_k(np.array([1.0, 0.0], dtype="float32"), k=4)
    assert results == []
    store.close()
