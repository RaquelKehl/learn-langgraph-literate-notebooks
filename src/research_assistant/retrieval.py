"""Retrieval with rare words weighted above common ones (NB 03).

A document's relevance is the sum of the weights of the question's words
it contains. A word's weight is its inverse document frequency: the rarer
the word in the corpus, the more it says about relevance.

Two rules decide what is kept (P6, ADR 0007, measured on 5 October 2026):

1. If the question names a subject (capitalised words after the first,
   such as Solvane or AMSA), a document must contain one of those names.
   Word statistics alone cannot do this in a small corpus: "third quarter"
   is as rare as "Solvane".
2. A document must reach RELEVANCE_CUTOFF times the best match.
"""
from __future__ import annotations

import math
import re
from collections.abc import Iterable

from research_assistant.state import SourceDoc

RELEVANCE_CUTOFF = 0.6  # P6: measured valid range (0.56, 0.66], see ADR 0007

STOPWORDS = frozenset(
    "a an and are as at be by did do does for from how in is it its must of on "
    "or that the their this to under was were what which who with".split()
)

# Financial texts abbreviate periods; the search reads them in full.
PERIODS = {
    "q1": "first quarter",
    "q2": "second quarter",
    "q3": "third quarter",
    "q4": "fourth quarter",
    "h1": "first half",
    "h2": "second half",
    "fy": "financial year",
}


def _singular(token: str) -> str:
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokenize(text: str) -> set[str]:
    """Lower-case words of three or more characters, without stop words.

    Period abbreviations are expanded ("Q3" becomes "third quarter") and a
    trailing plural "s" is removed ("platforms" matches "platform").
    """
    words: list[str] = []
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        words.extend(PERIODS.get(word, word).split())
    return {_singular(word) for word in words if len(word) >= 3 and word not in STOPWORDS}


def subject_words(question: str) -> set[str]:
    """The names a question is about: capitalised words after the first.

    Period abbreviations such as "Q3" are capitalised but are not names.
    """
    words = re.findall(r"[A-Za-z][A-Za-z0-9]*", question)
    names = [word for word in words[1:] if word[0].isupper() and word.lower() not in PERIODS]
    return tokenize(" ".join(names))


def _document_tokens(doc: SourceDoc) -> set[str]:
    return tokenize(f"{doc['title']}\n{doc['text']}")


def word_weights(corpus: Iterable[SourceDoc]) -> dict[str, float]:
    """Inverse document frequency for every word in the corpus."""
    corpus = list(corpus)
    counts: dict[str, int] = {}
    for doc in corpus:
        for word in _document_tokens(doc):
            counts[word] = counts.get(word, 0) + 1
    total = len(corpus)
    return {word: math.log((total + 1) / (count + 1)) + 1 for word, count in counts.items()}


def relevance(query: str, doc: SourceDoc, weights: dict[str, float]) -> float:
    shared = tokenize(query) & _document_tokens(doc)
    return round(sum(weights.get(word, 0.0) for word in shared), 4)


def rank(query: str, corpus: Iterable[SourceDoc], weights: dict[str, float]) -> list[tuple[SourceDoc, float]]:
    """Documents that name the question's subject, with relevance above zero, best first."""
    subject = subject_words(query)
    scored = [
        (doc, relevance(query, doc, weights))
        for doc in corpus
        if not subject or subject & _document_tokens(doc)
    ]
    scored = [pair for pair in scored if pair[1] > 0]
    return sorted(scored, key=lambda pair: (-pair[1], pair[0]["source_id"]))


def retrieve(
    query: str,
    corpus: Iterable[SourceDoc],
    weights: dict[str, float],
    cutoff: float = RELEVANCE_CUTOFF,
) -> list[SourceDoc]:
    """Documents that name the subject and reach `cutoff` times the best match."""
    ranked = rank(query, corpus, weights)
    if not ranked:
        return []
    best = ranked[0][1]
    return [doc for doc, score in ranked if score >= cutoff * best]
