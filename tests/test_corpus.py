"""Guards for the finance corpus in data/corpus/topic_*/.

Every document plays a fixed role in a built-in test (see docs/CONCEPT.md,
sections 8 and 9). These checks keep later edits from breaking those roles silently.
"""
import datetime as dt
import re

import pytest

from research_assistant.tools import CORPUS_DIR, load_corpus

TOPIC_PATTERN = "topic_*/*.md"
FIELDS = ["source_id", "topic", "type", "publisher", "date", "authority_weight"]
EXPECTED_COUNTS = {
    "topic_a_quarterly_earnings": 3,
    "topic_b_merger": 3,
    "topic_c_regulatory_change": 4,
    "topic_d_outdated_data": 4,
    "topic_e_market_analysis": 4,
    "topic_f_unrelated_control": 3,
}
# Retrieval is substring keyword matching, so these terms must stay in one topic.
FENCED_TERMS = {
    "a": ["solvane", "svdy", "ebitda", "talgrund"],
    "b": ["talvero", "nordquist", "synergies", "rheinfeld", "helix"],
    "c": ["amsa", "crypto", "custody", "cold storage", "keller amsler", "basel finance daily"],
    "d": ["brunnhof", "dividend", "payout", "lindmatt", "helvetic business review"],
    "e": ["robo", "sdwa", "fee", "wealthtech", "fintech pulse"],
    "f": ["seewil", "garden", "choir", "cycling"],
}
COPIED_SENTENCE = (
    "The average robo-advisory fee in Switzerland has fallen to just 0.38% a year, "
    "according to the latest industry figures."
)

DOCS = load_corpus(pattern=TOPIC_PATTERN)
BY_ID = {doc.source_id: doc for doc in DOCS}


def _full_text(doc):
    return f"{doc.title}\n{doc.text}"


def _letter(doc):
    return doc.metadata["topic"].split("_")[1]


def test_folder_sizes():
    counts = {}
    for path in CORPUS_DIR.glob(TOPIC_PATTERN):
        counts[path.parent.name] = counts.get(path.parent.name, 0) + 1
    assert counts == EXPECTED_COUNTS


def test_source_ids_are_unique():
    assert len(BY_ID) == len(DOCS) == 21


@pytest.mark.parametrize("doc", DOCS, ids=lambda d: d.source_id)
def test_front_matter_schema(doc):
    keys = list(doc.metadata)
    assert keys[:6] == FIELDS
    assert keys[6:] in ([], ["based_on"])
    assert doc.source_id[0].lower() == _letter(doc)
    assert isinstance(doc.metadata["date"], dt.date)
    assert 0.0 <= doc.metadata["authority_weight"] <= 1.0
    assert doc.title and doc.title != doc.source_id, "body must open with a # title"
    assert not doc.text.startswith("#"), "only one # title per document"


@pytest.mark.parametrize("doc", [d for d in DOCS if "based_on" in d.metadata], ids=lambda d: d.source_id)
def test_based_on_points_to_older_source_in_same_topic(doc):
    for ref in doc.metadata["based_on"]:
        origin = BY_ID[ref]
        assert origin.metadata["topic"] == doc.metadata["topic"]
        assert origin.metadata["date"] <= doc.metadata["date"]


@pytest.mark.parametrize("doc", DOCS, ids=lambda d: d.source_id)
def test_fenced_terms_stay_in_their_topic(doc):
    text = _full_text(doc).lower()
    for letter, terms in FENCED_TERMS.items():
        if letter == _letter(doc):
            continue
        leaked = [t for t in terms if t in text]
        assert not leaked, f"{doc.source_id} uses topic {letter} terms {leaked}"


@pytest.mark.parametrize("doc", DOCS, ids=lambda d: d.source_id)
def test_no_dashes_as_punctuation(doc):
    assert not re.search(r"[–—]| - ", _full_text(doc))


def test_topic_a_contradiction_on_revenue():
    assert "CHF 342 million" in BY_ID["A1"].text
    assert "CHF 342 million" in BY_ID["A2"].text
    assert "CHF 310 million" in BY_ID["A3"].text
    assert BY_ID["A3"].metadata["authority_weight"] < 0.5


def test_topic_c_has_one_usable_source():
    assert BY_ID["C1"].metadata["authority_weight"] >= 0.5
    for sid in ("C2", "C3", "C4"):
        doc = BY_ID[sid]
        assert doc.metadata["authority_weight"] < 0.5
        assert "%" not in doc.text and "2026" not in doc.text


def test_topic_d_old_and_new_targets():
    for sid in ("D1", "D4"):
        assert "60%" in BY_ID[sid].text and BY_ID[sid].metadata["date"].year == 2023
    for sid in ("D2", "D3"):
        assert "45%" in BY_ID[sid].text and BY_ID[sid].metadata["date"].year == 2025


def test_topic_e_copied_figure_and_true_average():
    assert COPIED_SENTENCE in BY_ID["E1"].text
    assert COPIED_SENTENCE in BY_ID["E2"].text
    assert BY_ID["E2"].metadata["based_on"] == ["E1"]
    assert "0.62%" in BY_ID["E3"].text


# Words of the canonical topic e question; E4 must avoid them so that only
# the rephrased query of round 2 finds it (ADR 0007).
ROUND_ONE_TERMS_E = ["robo", "fee", "average", "advisory", "platform", "swiss", "annual"]


def test_topic_e_independent_source_needs_rephrased_query():
    doc = BY_ID["E4"]
    assert doc.metadata["authority_weight"] >= 0.5
    assert "based_on" not in doc.metadata
    assert "0.62%" in doc.text
    found = [t for t in ROUND_ONE_TERMS_E if t in _full_text(doc).lower()]
    assert not found, f"E4 would be found in round 1 through {found}"


def test_topic_f_has_neutral_authority():
    for sid in ("F1", "F2", "F3"):
        assert BY_ID[sid].metadata["authority_weight"] == 0.5
