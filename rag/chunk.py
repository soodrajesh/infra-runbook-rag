"""Split markdown files into (source_file, section, text) chunks on headers."""

from dataclasses import dataclass
from pathlib import Path
import fnmatch
import os
import re

HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)$")

# Directories that are never docs, even if they happen to contain a *.md file
# (e.g. a vendored package's README inside .venv/node_modules).
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "dist", "build"}

# Long sections get one embedding vector per section, diluting specific commands buried in
# prose. Splitting further keeps each vector focused enough for retrieval to find the exact
# paragraph a question is about.
MAX_CHUNK_CHARS = 600


def _split_long_text(text: str, max_chars: int) -> list[str]:
    """Split text into paragraph-packed chunks up to max_chars, never splitting a paragraph
    (or a fenced code block) in half."""
    paragraphs: list[str] = []
    current: list[str] = []
    in_code_block = False

    for line in text.split("\n"):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            current.append(line)
            continue
        if line.strip() == "" and not in_code_block:
            if current:
                paragraphs.append("\n".join(current).strip())
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append("\n".join(current).strip())
    paragraphs = [p for p in paragraphs if p]

    if not paragraphs:
        return []

    parts: list[str] = []
    buf: list[str] = []
    buf_len = 0
    for para in paragraphs:
        added_len = len(para) + (2 if buf else 0)
        if buf and buf_len + added_len > max_chars:
            parts.append("\n\n".join(buf))
            buf, buf_len = [para], len(para)
        else:
            buf.append(para)
            buf_len += added_len
    if buf:
        parts.append("\n\n".join(buf))

    return parts


@dataclass
class Chunk:
    source_file: str
    section: str
    text: str


def chunk_markdown(path: Path, root: Path) -> list[Chunk]:
    """Split a single markdown file into per-section chunks.

    Text before the first header is kept under the filename itself as the
    section name, since README-style docs often open with unheaded intro text.
    """
    source_file = str(path.relative_to(root))
    lines = path.read_text(encoding="utf-8").splitlines()

    chunks: list[Chunk] = []
    section = path.name
    buf: list[str] = []
    in_code_block = False

    def flush() -> None:
        text = "\n".join(buf).strip()
        if not text:
            return

        parts = _split_long_text(text, MAX_CHUNK_CHARS)
        if len(parts) <= 1:
            chunks.append(Chunk(source_file=source_file, section=section, text=text))
        else:
            for i, part in enumerate(parts):
                part_section = f"{section} (part {i + 1}/{len(parts)})"
                chunks.append(Chunk(source_file=source_file, section=part_section, text=part))

    for line in lines:
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            buf.append(line)
            continue

        match = None if in_code_block else HEADER_RE.match(line)
        if match:
            flush()
            section = match.group(2).strip()
            buf = []
        else:
            buf.append(line)
    flush()

    return chunks


def chunk_repo(root: Path, glob: str = "*.md") -> list[Chunk]:
    matches: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            if fnmatch.fnmatch(filename, glob):
                matches.append(Path(dirpath) / filename)

    chunks: list[Chunk] = []
    for path in sorted(matches):
        chunks.extend(chunk_markdown(path, root))
    return chunks
