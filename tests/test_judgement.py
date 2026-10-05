"""Stage 5 (NB 05): the model's own judgement against the rules.

The verdicts were recorded from qwen3:8b; these tests pin what that model
did with this prompt and corpus, not what every model would do.
"""
import pytest

from research_assistant.assistant import corpus, extract_claim, weights
from research_assistant.evidence import CANONICAL_QUESTIONS, assess
from research_assistant.judgement import (
    LISTING_JUDGE_PROMPT,
    Verdict,
    compare,
    format_documents,
    judge,
    origins_stating,
    read_verdict,
)
from research_assistant.models import get_chat_model
from research_assistant.retrieval import retrieve

LLM = get_chat_model("fake", fixture=("nb03_claims.yaml", "nb05_judgements.yaml"))
BY_ID = {doc["source_id"]: doc for doc in corpus()}
CASES = {topic: retrieve(CANONICAL_QUESTIONS[topic], corpus(), weights()) for topic in "abde"}
CASES["e_copies"] = [BY_ID["E1"], BY_ID["E2"]]


def _disagreements(case, **kwargs):
    question = CANONICAL_QUESTIONS[case[0]]
    docs = CASES[case]
    claims = {doc["source_id"]: extract_claim(LLM, question, doc) for doc in docs}
    verdict = judge(LLM, question, docs, **kwargs)
    return {field for field, _, _, agree in compare(verdict, assess(docs, claims), docs, claims) if not agree}


EXPECTED_FIRST_PROMPT = {
    "a": {"contradiction"},
    "b": set(),
    "d": {"contradiction"},
    "e": {"contradiction", "sufficient"},
    "e_copies": {"answer", "independent sources for that answer", "sufficient"},
}


@pytest.mark.parametrize("case", EXPECTED_FIRST_PROMPT)
@pytest.mark.parametrize("with_metadata", [True, False])
def test_first_prompt_disagreements(case, with_metadata):
    assert _disagreements(case, with_metadata=with_metadata) == EXPECTED_FIRST_PROMPT[case]


def test_listing_prompt_moves_errors_rather_than_removing_them():
    assert _disagreements("a", prompt=LISTING_JUDGE_PROMPT) == {"contradiction"}
    assert _disagreements("e", prompt=LISTING_JUDGE_PROMPT) == set()
    assert _disagreements("d", prompt=LISTING_JUDGE_PROMPT) == {"sufficient"}
    assert _disagreements("e_copies", prompt=LISTING_JUDGE_PROMPT) == {"answer", "sufficient"}


def test_copies_are_one_origin():
    claims = {"E1": "0.38%", "E2": "0.38%"}
    assert origins_stating("0.38%", CASES["e_copies"], claims) == 1


def test_metadata_block_names_the_copy_source():
    assert "based on: E1" in format_documents([BY_ID["E2"]])
    assert "(publisher:" not in format_documents([BY_ID["E2"]], with_metadata=False)


def test_read_verdict_accepts_numbers_and_fences():
    verdict = read_verdict('```json\n{"answer": 0.38, "contradiction": false, "independent_sources": 2, '
                           '"outdated": [], "sufficient": true, "reason": "x"}\n```')
    assert verdict == Verdict("0.38", False, 2, [], True, "x")
