"""Streamlit UI for infra-runbook-rag. Run with: streamlit run ui.py"""

import os
from pathlib import Path

import streamlit as st

from rag.ask import answer_from_chunks, retrieve
from rag.chunk import chunk_repo
from rag.embed import embed
from rag.store import Store

DB_PATH = Path("rag.db")

st.set_page_config(page_title="infra-runbook-rag", page_icon="📚")
st.title("infra-runbook-rag")
st.caption("Ask on-call-style questions over an infra repo's own markdown docs, with citations.")


@st.cache_resource
def get_openai_client():
    import openai

    return openai.OpenAI()


with st.sidebar:
    st.header("1. Ingest a repo")
    repo_path = st.text_input("Repo path", value="../minikube-gitops-platform")
    glob = st.text_input("Glob", value="*.md")
    if st.button("Ingest"):
        with st.spinner("Chunking and embedding..."):
            chunks = chunk_repo(Path(repo_path), glob=glob)
            if not chunks:
                st.warning(f"No files matching {glob!r} found under {repo_path}")
            else:
                embeddings = embed([c.text for c in chunks])
                store = Store(DB_PATH)
                store.clear()
                store.add(chunks, embeddings)
                store.close()
                st.success(f"Stored {len(chunks)} chunks in {DB_PATH}")

    if DB_PATH.exists():
        with Store(DB_PATH) as store:
            count = store.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        st.caption(f"Current store: {count} chunks in {DB_PATH}")
    else:
        st.caption("No store yet — ingest a repo first.")

st.header("2. Ask a question")
question = st.text_input("Question", placeholder="how do I rotate the sealing key?")
k = st.slider("Chunks to retrieve", min_value=1, max_value=10, value=6)

if st.button("Ask", type="primary"):
    if not DB_PATH.exists():
        st.error("No store found — ingest a repo first (sidebar).")
    elif not os.environ.get("OPENAI_API_KEY"):
        st.error("OPENAI_API_KEY is not set in your environment.")
    elif not question.strip():
        st.warning("Enter a question first.")
    else:
        with st.spinner("Retrieving and asking..."):
            with Store(DB_PATH) as store:
                chunks = retrieve(store, question, k=k)
            result = answer_from_chunks(get_openai_client(), chunks, question)

        st.markdown("### Answer")
        st.write(result)

        with st.expander(f"Retrieved {len(chunks)} chunks (by cosine score)"):
            for c in chunks:
                st.markdown(f"**{c.score:.3f}** — `[{c.source_file} § {c.section}]`")
                st.text(c.text)
                st.divider()
