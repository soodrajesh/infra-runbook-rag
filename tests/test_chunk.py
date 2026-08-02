from pathlib import Path

from rag.chunk import chunk_markdown, chunk_repo


def test_chunk_markdown_splits_on_headers(tmp_path: Path):
    doc = tmp_path / "RUNBOOK.md"
    doc.write_text(
        "\n".join(
            [
                "Intro text before any header.",
                "",
                "## Rotate the sealing key",
                "Back up the key regularly.",
                "",
                "## Troubleshooting 502s",
                "Check the NetworkPolicy allows traffic from app to backend.",
            ]
        )
    )

    chunks = chunk_markdown(doc, tmp_path)

    assert [c.section for c in chunks] == [
        "RUNBOOK.md",
        "Rotate the sealing key",
        "Troubleshooting 502s",
    ]
    assert chunks[0].text == "Intro text before any header."
    assert "Back up the key" in chunks[1].text
    assert "NetworkPolicy" in chunks[2].text
    assert all(c.source_file == "RUNBOOK.md" for c in chunks)


def test_chunk_markdown_skips_empty_sections(tmp_path: Path):
    doc = tmp_path / "doc.md"
    doc.write_text("## Empty\n\n## Has content\nsomething\n")

    chunks = chunk_markdown(doc, tmp_path)

    assert [c.section for c in chunks] == ["Has content"]


def test_chunk_markdown_ignores_hash_comments_in_code_blocks(tmp_path: Path):
    doc = tmp_path / "RUNBOOK.md"
    doc.write_text(
        "\n".join(
            [
                "## Verify",
                "```bash",
                "# All seven Applications should show Synced / Healthy",
                "kubectl get applications -n argocd",
                "```",
                "",
                "## Troubleshooting",
                "check the logs",
            ]
        )
    )

    chunks = chunk_markdown(doc, tmp_path)

    assert [c.section for c in chunks] == ["Verify", "Troubleshooting"]
    assert "# All seven Applications" in chunks[0].text
    assert "kubectl get applications" in chunks[0].text


def test_chunk_repo_walks_glob(tmp_path: Path):
    (tmp_path / "README.md").write_text("## A\ntext a\n")
    sub = tmp_path / "docs"
    sub.mkdir()
    (sub / "SECURITY.md").write_text("## B\ntext b\n")
    (tmp_path / "notes.txt").write_text("ignored")

    chunks = chunk_repo(tmp_path, glob="*.md")

    sources = {c.source_file for c in chunks}
    assert sources == {"README.md", "docs/SECURITY.md"}


def test_chunk_repo_skips_vendor_dirs(tmp_path: Path):
    (tmp_path / "README.md").write_text("## A\ntext a\n")
    for vendor_dir in (".venv", "node_modules", ".git", "__pycache__"):
        vendored = tmp_path / vendor_dir / "some_pkg"
        vendored.mkdir(parents=True)
        (vendored / "README.md").write_text("## Vendored\nshould not be ingested\n")

    chunks = chunk_repo(tmp_path, glob="*.md")

    sources = {c.source_file for c in chunks}
    assert sources == {"README.md"}
