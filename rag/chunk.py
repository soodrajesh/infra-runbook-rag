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
        if text:
            chunks.append(Chunk(source_file=source_file, section=section, text=text))

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
