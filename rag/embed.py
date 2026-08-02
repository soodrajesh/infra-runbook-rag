"""Local embedding model wrapper (loaded once, reused across calls)."""

from functools import lru_cache

import numpy as np

MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def embed(texts: list[str]) -> np.ndarray:
    """Embed a list of strings, returning an (N, dim) float32 array."""
    return _model().encode(texts, normalize_embeddings=True, convert_to_numpy=True).astype("float32")
