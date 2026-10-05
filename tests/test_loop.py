"""Stage 4 (NB 04): routing and the bounded search loop.

Expected rounds per topic come from ADR 0007: a, b and d need one round,
topic e is rescued in round 2, topic c exhausts all three rounds.
"""
import operator
from typing import Annotated, TypedDict

import pytest
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph

from research_assistant import loop
from research_assistant.assistant import collect_primary, collect_secondary, extract_claim
from research_assistant.evidence import CANONICAL_QUESTIONS, assess
from research_assistant.models import get_chat_model
from research_assistant.state import ResearchState, SourceDoc, check_contract, merge_claims, merge_documents

LLM = get_chat_model("fake", fixture=("nb03_claims.yaml", "nb04_queries.yaml"))
GRAPH = loop.build_loop_graph(LLM)
RESULTS = {topic: GRAPH.invoke({"question": q}) for topic, q in CANONICAL_QUESTIONS.items()}

EXPECTED_ROUNDS = {"a": 1, "b": 1, "c": 3, "d": 1, "e": 2}


@pytest.mark.parametrize("topic", EXPECTED_ROUNDS)
def test_rounds_per_topic(topic):
    assert RESULTS[topic].get("retrieval_round", 1) == EXPECTED_ROUNDS[topic]


def test_topic_e_is_rescued_in_round_two():
    answer = RESULTS["e"]["draft_answer"]
    assert answer.startswith(
        "0.62% (sources: E3, E4; evidence score 1.65). "
        "The quality gate was passed in search round 2, after a rephrased search found E4."
    )
    assert sorted(RESULTS["e"]["claims"]) == ["E1", "E2", "E3", "E4"]


def test_topic_c_stops_with_a_stated_limitation():
    answer = RESULTS["c"]["draft_answer"]
    assert answer.startswith("Limited answer after 3 of 3 search rounds: 90% rests on C1 only")
    assert "No further search will run." in answer
    assert "Documents found: C1, C2, C3, C4." in answer


@pytest.mark.parametrize("topic", CANONICAL_QUESTIONS)
def test_answer_route_implies_a_state_that_supports_it(topic):
    # Invariant: whenever the router chose "answer", re-assessing the final
    # state's documents and claims must also pass the gate. Unmerged claims
    # (NB04-E03) break exactly this.
    final = RESULTS[topic]
    if loop.route(final) == "answer":
        assert assess(final["documents"], final["claims"]).sufficient


@pytest.mark.parametrize("topic", CANONICAL_QUESTIONS)
def test_loop_keeps_its_contract(topic):
    check_contract(GRAPH.stream({"question": CANONICAL_QUESTIONS[topic]}), loop.LOOP_CONTRACT)


@pytest.mark.parametrize(
    ("score", "rounds", "label"),
    [(1.6, None, "answer"), (0.85, None, "search_again"), (0.95, 2, "search_again"), (0.95, 3, "limit_answer")],
)
def test_route_reads_score_and_round(score, rounds, label):
    state = {"evidence_score": score}
    if rounds:
        state["retrieval_round"] = rounds
    assert loop.route(state) == label


def test_clean_query_strips_quotes_and_extra_lines():
    assert loop.clean_query('  "a query"\nsecond line') == "a query"


def test_merge_claims_keeps_first_claims_and_adds_new_ones():
    assert merge_claims({"E3": "0.62%"}, {"E3": "changed", "E4": "0.62%"}) == {"E3": "0.62%", "E4": "0.62%"}


class _NoMergeState(TypedDict, total=False):
    question: str
    query: str
    retrieval_round: int
    documents: Annotated[list[SourceDoc], merge_documents]
    claims: dict[str, str | None]
    evidence_score: float
    history: Annotated[list[str], operator.add]


def test_nb04_e03_claims_without_reducer_lose_round_one():
    def collect(state: _NoMergeState) -> dict:
        return collect_primary(state) | {"documents": collect_primary(state)["documents"] + collect_secondary(state)["documents"]}

    def score(state: _NoMergeState) -> dict:
        known = state.get("claims") or {}
        new = {d["source_id"]: extract_claim(LLM, state["question"], d) for d in state["documents"] if d["source_id"] not in known}
        return {"claims": new, "evidence_score": assess(state["documents"], {**known, **new}).evidence_score}

    def refine(state: _NoMergeState) -> dict:
        return loop.make_refine_query(LLM)(state)

    builder = StateGraph(_NoMergeState)
    builder.add_node("collect", collect)
    builder.add_node("score", score)
    builder.add_node("refine_query", refine)
    builder.add_edge(START, "collect")
    builder.add_edge("collect", "score")
    # an untyped wrapper: loop.route's type hint would bind it to ResearchState
    builder.add_conditional_edges("score", lambda s: loop.route(s), {"answer": END, "search_again": "refine_query", "limit_answer": END})
    builder.add_edge("refine_query", "collect")
    result = builder.compile().invoke({"question": CANONICAL_QUESTIONS["e"]})
    assert result["retrieval_round"] == 2  # the router saw the full claims and chose "answer"
    assert sorted(result["claims"]) == ["E4"]  # but round 1's claims were replaced afterwards
    # whoever reads the state now cannot support the answer the router chose
    assert not assess(result["documents"], result["claims"]).sufficient


def test_nb04_e01_loop_without_stop_condition():
    def score(state: ResearchState) -> dict:
        return {"evidence_score": 0.95}

    def refine(state: ResearchState) -> dict:
        return {"retrieval_round": state.get("retrieval_round", 1) + 1}

    builder = StateGraph(ResearchState)
    builder.add_node("score", score)
    builder.add_node("refine_query", refine)
    builder.add_edge(START, "score")
    builder.add_conditional_edges("score", lambda s: "search_again", {"search_again": "refine_query"})
    builder.add_edge("refine_query", "score")
    with pytest.raises(GraphRecursionError):
        builder.compile().invoke({"question": "q"}, {"recursion_limit": 12})


def test_nb04_e02_router_returns_an_unknown_label():
    def score(state: ResearchState) -> dict:
        return {"evidence_score": 0.95}

    builder = StateGraph(ResearchState)
    builder.add_node("score", score)
    builder.add_node("write_answer", lambda s: {"draft_answer": "x"})
    builder.add_edge(START, "score")
    builder.add_conditional_edges("score", lambda s: "search_again", {"answer": "write_answer"})
    builder.add_edge("write_answer", END)
    with pytest.raises(KeyError):
        builder.compile().invoke({"question": "q"})


def test_naive_rephrasing_finds_nothing_new():
    from langchain_core.prompts import ChatPromptTemplate

    from research_assistant.assistant import corpus, weights
    from research_assistant.retrieval import retrieve

    naive = ChatPromptTemplate.from_template("Rephrase the question as a search query.\n\nQuestion: {question}")
    query = loop.clean_query(LLM.invoke(naive.invoke({"question": CANONICAL_QUESTIONS["e"]})).content)
    assert "E4" not in {d["source_id"] for d in retrieve(query, corpus(), weights())}
