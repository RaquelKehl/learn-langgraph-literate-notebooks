"""Stage 3 (NB 03): the evidence rules and the research graph.

Expected outcomes per topic come from ADR 0007 (round 1 only; NB 04 adds
the further rounds that rescue topic e and exhaust topic c).
"""
import copy

import pytest

from research_assistant import assistant
from research_assistant.evidence import (
    CANONICAL_QUESTIONS,
    assess,
    format_figure,
    parse_figure,
    read_claim,
)
from research_assistant.models import get_chat_model
from research_assistant.state import check_contract

LLM = get_chat_model("fake", fixture="nb03_claims.yaml")
GRAPH = assistant.build_research_graph(LLM)
RESULTS = {topic: GRAPH.invoke({"question": q}) for topic, q in CANONICAL_QUESTIONS.items()}

EXPECTED = {
    #      score  contradiction  answer starts with
    "a": (1.6, True, "CHF 342 million (sources: A1, A2"),
    "b": (2.55, False, "CHF 1.2 billion (sources: B1, B2, B3"),
    "c": (0.95, False, "Evidence insufficient: 90% rests on C1 only"),
    "d": (1.65, True, "45% (sources: D2, D3"),
    "e": (0.85, True, "Evidence insufficient: 0.62% rests on E3 only"),
}


@pytest.mark.parametrize("topic", EXPECTED)
def test_outcome_per_topic(topic):
    score, contradiction, answer = EXPECTED[topic]
    result = RESULTS[topic]
    assert result["evidence_score"] == score
    assert result["contradiction_flag"] is contradiction
    assert result["draft_answer"].startswith(answer)


def test_reasons_for_disregarded_sources_are_stated():
    assert "A3 disregarded: below the authority floor" in RESULTS["a"]["draft_answer"]
    assert "D1 disregarded: outdated: superseded by D2" in RESULTS["d"]["draft_answer"]
    assert "C2 disregarded: states no figure" in RESULTS["c"]["draft_answer"]


@pytest.mark.parametrize("topic", CANONICAL_QUESTIONS)
def test_research_graph_keeps_its_contract(topic):
    check_contract(GRAPH.stream({"question": CANONICAL_QUESTIONS[topic]}), assistant.RESEARCH_CONTRACT)


def test_collectors_split_primary_and_secondary_sources():
    state = {"question": CANONICAL_QUESTIONS["a"]}
    primary = {d["source_id"] for d in assistant.collect_primary(state)["documents"]}
    secondary = {d["source_id"] for d in assistant.collect_secondary(state)["documents"]}
    assert primary == {"A1"} and secondary == {"A2", "A3"}


def test_e4_rescues_topic_e_once_it_is_found():
    docs = RESULTS["e"]["documents"] + [assistant.corpus()[[d["source_id"] for d in assistant.corpus()].index("E4")]]
    claims = {**RESULTS["e"]["claims"], "E4": "0.62%"}
    result = assess(docs, claims)
    assert result.sufficient and result.supporting == ["E3", "E4"] and result.evidence_score == 1.65


def test_a_copy_counts_once_even_above_the_floor():
    docs = copy.deepcopy(RESULTS["e"]["documents"])
    for doc in docs:
        if doc["source_id"] in ("E1", "E2"):
            doc["authority_weight"] = 0.7  # suppose the blog and the newsletter were reputable
    result = assess(docs, RESULTS["e"]["claims"])
    assert result.unresolved  # 0.38% (E1, E2) against 0.62% (E3): two qualifying figures
    only_copies = [d for d in docs if d["source_id"] in ("E1", "E2")]
    result = assess(only_copies, {"E1": "0.38%", "E2": "0.38%"})
    assert result.supporting == ["E1"] and "copy: rests on E1" in result.disregarded["E2"]
    assert not result.sufficient


def test_two_credible_sources_disagreeing_leave_no_answer():
    docs = copy.deepcopy(RESULTS["a"]["documents"])
    claims = {**RESULTS["a"]["claims"], "A2": "CHF 320 million"}
    result = assess(docs, claims)
    assert result.unresolved and result.evidence_score == 0.0 and result.answer is None


def test_reading_and_parsing_figures():
    assert read_claim('{"figure": "CHF 342 million"}') == "CHF 342 million"
    assert read_claim('```json\n{"figure": null}\n```') is None
    assert parse_figure("CHF 1.2 billion") == (1.2e9, "CHF")
    assert parse_figure("0.62% of assets") == parse_figure("0.62%")
    assert format_figure(parse_figure("CHF 342 million")) == "CHF 342 million"


def test_prompt_log_first_version_replies_are_prose():
    from langchain_core.prompts import ChatPromptTemplate

    first = ChatPromptTemplate.from_template(
        "Which figure does the document give in answer to the question?\n\n"
        "Question: {question}\n\nDocument: {document}"
    )
    a3 = next(d for d in RESULTS["a"]["documents"] if d["source_id"] == "A3")
    reply = LLM.invoke(first.invoke({"question": CANONICAL_QUESTIONS["a"], "document": f"{a3['title']}\n\n{a3['text']}"}))
    assert "CHF 310 million" in reply.content and "CHF 342 million" in reply.content
    with pytest.raises(ValueError):
        read_claim(reply.content)
