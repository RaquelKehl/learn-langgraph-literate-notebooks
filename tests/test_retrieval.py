"""P6 (ADR 0007): which documents each query retrieves.

The queries are the canonical questions of topics a to e plus the round 2
and round 3 queries that qwen3:8b actually wrote for topics c and e
(recorded for NB 04).
"""
import pytest

from research_assistant.retrieval import (
    RELEVANCE_CUTOFF,
    rank,
    retrieve,
    subject_words,
    tokenize,
    word_weights,
)
from research_assistant.tools import load_corpus, to_source_doc

CORPUS = [to_source_doc(doc) for doc in load_corpus()]
WEIGHTS = word_weights(CORPUS)

EXPECTED = {
    "What revenue did Solvane Dynamics report for the third quarter of 2025?": {"A1", "A2", "A3"},
    "What is the implied transaction value of the merger between Talvero Bank and Nordquist Privatbank?": {"B1", "B2", "B3"},
    "What share of client crypto assets must be kept in cold storage under the new AMSA custody rules?": {"C1", "C2", "C3", "C4"},
    "What is Brunnhof Versicherungen's current dividend payout target?": {"D1", "D2", "D3", "D4"},
    "What is the average annual fee of robo-advisory platforms in Switzerland in 2025?": {"E1", "E2", "E3"},
    "What is the typical yearly charge of automated investment services in Switzerland for 2025?": {"E3", "E4"},
    "What percentage of client cryptocurrency holdings is required to be stored in offline wallets according to the updated AMSA custody regulations?": {"C1", "C3"},
    "Regulatory requirements for crypto asset custody in cold storage under AMSA rules": {"C1", "C2", "C3", "C4"},
}


def _ids(documents):
    return {doc["source_id"] for doc in documents}


@pytest.mark.parametrize("query", EXPECTED, ids=[q[:40] for q in EXPECTED])
def test_query_retrieves_exactly_the_expected_documents(query):
    assert _ids(retrieve(query, CORPUS, WEIGHTS)) == EXPECTED[query]


def test_control_topic_is_never_retrieved():
    for query in EXPECTED:
        assert not any(doc_id.startswith("F") for doc_id in _ids(retrieve(query, CORPUS, WEIGHTS)))


def test_without_a_cutoff_the_control_topic_leaks():
    # NB03-E01: everything that shares any word, nothing filtered.
    leaked = _ids(retrieve(next(iter(EXPECTED)), CORPUS, WEIGHTS, cutoff=0.0))
    assert "F1" not in leaked  # the subject rule alone already keeps F1 out
    no_subject = "What revenue was reported for the third quarter of 2025?"
    assert "F1" in _ids(retrieve(no_subject, CORPUS, WEIGHTS, cutoff=0.0))


def test_e4_needs_the_rephrased_query():
    first, second = list(EXPECTED)[4], list(EXPECTED)[5]
    assert "E4" not in _ids(retrieve(first, CORPUS, WEIGHTS))
    assert "E4" in _ids(retrieve(second, CORPUS, WEIGHTS))


def test_cutoff_sits_inside_the_measured_range():
    assert 0.56 < RELEVANCE_CUTOFF <= 0.66


def test_period_abbreviations_are_expanded():
    assert {"third", "quarter"} <= tokenize("Solvane Q3 numbers")


def test_subject_words_are_the_capitalised_names():
    assert subject_words("What revenue did Solvane Dynamics report for Q3?") == {"solvane", "dynamic"}
    assert subject_words("Which rules on crypto assets apply to banks?") == set()


def test_ranking_is_deterministic():
    query = next(iter(EXPECTED))
    assert rank(query, CORPUS, WEIGHTS) == rank(query, list(reversed(CORPUS)), WEIGHTS)
