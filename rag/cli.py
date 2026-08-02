import os
from pathlib import Path

import click

from .ask import answer
from .chunk import chunk_repo
from .embed import embed
from .store import Store

DEFAULT_DB = Path("rag.db")


@click.group()
def cli():
    """RAG over infra docs/runbooks."""


@cli.command()
@click.argument("repo_path", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--glob", default="*.md", show_default=True, help="Glob pattern for docs to ingest.")
@click.option("--db", "db_path", default=DEFAULT_DB, type=click.Path(path_type=Path), show_default=True)
def ingest(repo_path: Path, glob: str, db_path: Path):
    """Chunk and embed all docs matching GLOB under REPO_PATH into the local store."""
    chunks = chunk_repo(repo_path, glob=glob)
    if not chunks:
        click.echo(f"No files matching {glob!r} found under {repo_path}")
        return

    click.echo(f"Embedding {len(chunks)} chunks from {repo_path} ...")
    embeddings = embed([c.text for c in chunks])

    store = Store(db_path)
    store.clear()
    store.add(chunks, embeddings)
    store.close()
    click.echo(f"Stored {len(chunks)} chunks in {db_path}")


@cli.command()
@click.argument("question")
@click.option("--db", "db_path", default=DEFAULT_DB, type=click.Path(path_type=Path), show_default=True)
@click.option("-k", default=4, show_default=True, help="Number of chunks to retrieve.")
def ask(question: str, db_path: Path, k: int):
    """Ask QUESTION against the ingested docs."""
    if not Path(db_path).exists():
        raise click.ClickException(f"{db_path} not found — run `rag ingest <repo_path>` first.")

    if not os.environ.get("OPENAI_API_KEY"):
        raise click.ClickException("OPENAI_API_KEY is not set.")

    import openai

    client = openai.OpenAI()
    store = Store(db_path)
    result = answer(client, store, question, k=k)
    store.close()
    click.echo(result)


if __name__ == "__main__":
    cli()
