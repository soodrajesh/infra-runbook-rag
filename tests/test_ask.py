from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from rag import ask as ask_module
from rag.chunk import Chunk
from rag.store import Store


@pytest.fixture
def populated_store(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    chunks = [
        Chunk(source_file="RUNBOOK.md", section="Troubleshooting 502s", text="Check the NetworkPolicy."),
    ]
    embeddings = np.array([[1.0, 0.0]], dtype="float32")
    store.add(chunks, embeddings)
    yield store
    store.close()


def test_answer_cites_source_in_prompt(monkeypatch, populated_store):
    monkeypatch.setattr(ask_module, "embed", lambda texts: np.array([[1.0, 0.0]], dtype="float32"))

    fake_response = MagicMock()
    fake_response.choices = [
        MagicMock(message=MagicMock(content="502s are caused by a NetworkPolicy issue [RUNBOOK.md § Troubleshooting 502s]"))
    ]
    client = MagicMock()
    client.chat.completions.create.return_value = fake_response

    result = ask_module.answer(client, populated_store, "why 502?", k=1)

    assert "RUNBOOK.md § Troubleshooting 502s" in result
    sent_prompt = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "RUNBOOK.md § Troubleshooting 502s" in sent_prompt
    assert "Check the NetworkPolicy." in sent_prompt


def test_answer_handles_none_content(monkeypatch, populated_store):
    monkeypatch.setattr(ask_module, "embed", lambda texts: np.array([[1.0, 0.0]], dtype="float32"))

    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content=None))]
    client = MagicMock()
    client.chat.completions.create.return_value = fake_response

    result = ask_module.answer(client, populated_store, "why 502?", k=1)

    assert "no content" in result.lower()


def test_answer_handles_empty_store(tmp_path):
    store = Store(tmp_path / "empty.db")
    client = MagicMock()

    result = ask_module.answer(client, store, "anything?")

    assert "ingest" in result.lower()
    client.chat.completions.create.assert_not_called()
    store.close()
