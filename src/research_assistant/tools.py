"""Deterministic access to the local corpus in data/corpus/topic_*/.

No network access: every document is a versioned Markdown file with YAML
front matter. Retrieval and scoring are built on top of this in NB 03.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from research_assistant.state import SourceDoc

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = PROJECT_ROOT / "data" / "corpus"
TOPIC_PATTERN = "topic_*/*.md"

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass(frozen=True)
class Document:
    source_id: str
    title: str
    text: str
    metadata: dict = field(default_factory=dict)


def load_corpus(corpus_dir: Path = CORPUS_DIR, pattern: str = TOPIC_PATTERN) -> list[Document]:
    """Load every corpus document, sorted by path.

    The title is the document's single `#` heading; `text` is the body
    below it.
    """
    documents = []
    for path in sorted(corpus_dir.glob(pattern)):
        raw = path.read_text(encoding="utf-8")
        match = _FRONTMATTER.match(raw)
        metadata = yaml.safe_load(match.group(1)) if match else {}
        body = (raw[match.end():] if match else raw).strip()
        title, _, text = body.partition("\n")
        documents.append(
            Document(
                source_id=str(metadata.get("source_id", path.stem)),
                title=title.removeprefix("# ").strip(),
                text=text.strip(),
                metadata=metadata or {},
            )
        )
    if not documents:
        raise FileNotFoundError(f"No corpus documents found in {corpus_dir}")
    return documents


def to_source_doc(doc: Document) -> SourceDoc:
    """The form in which a document travels through the graph's state."""
    meta = doc.metadata
    return SourceDoc(
        source_id=doc.source_id,
        title=doc.title,
        topic=meta["topic"],
        type=meta["type"],
        publisher=meta["publisher"],
        date=meta["date"].isoformat(),
        authority_weight=float(meta["authority_weight"]),
        based_on=list(meta.get("based_on", [])),
        text=doc.text,
    )
