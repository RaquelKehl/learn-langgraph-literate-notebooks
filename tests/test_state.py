"""Stage 2 (NB 02): reducers, the state contract and the skeleton graph."""
import operator
from typing import Annotated, TypedDict

import pytest
from langgraph.errors import InvalidUpdateError
from langgraph.graph import END, START, StateGraph

from research_assistant import skeleton
from research_assistant.skeleton import source
from research_assistant.state import (
    ContractViolation,
    ResearchState,
    check_contract,
    merge_documents,
)


def _ids(documents):
    return [doc["source_id"] for doc in documents]


def test_merge_documents_deduplicates_and_sorts():
    a1, a2 = source("A1"), source("A2")
    assert _ids(merge_documents([a2], [a1, a2])) == ["A1", "A2"]


def test_merge_documents_handles_empty_and_missing_lists():
    a1 = source("A1")
    assert merge_documents(None, [a1]) == [a1]
    assert merge_documents([a1], None) == [a1]
    assert merge_documents([], []) == []


def test_skeleton_merges_parallel_writes_deterministically():
    graph = skeleton.build_skeleton_graph()
    first = graph.invoke({"question": skeleton.QUESTION})
    assert first == graph.invoke({"question": skeleton.QUESTION})
    assert _ids(first["documents"]) == ["A1", "A2"]
    assert first["evidence_score"] == 1.6
    assert first["contradiction_flag"] is False
    assert first["draft_answer"] == "2 documents collected (A1, A2), evidence score 1.6."
    assert len(first["history"]) == 4


def test_skeleton_keeps_its_contract():
    updates = list(skeleton.build_skeleton_graph().stream({"question": skeleton.QUESTION}))
    check_contract(updates, skeleton.SKELETON_CONTRACT)


def test_contract_rejects_writes_by_non_owners_and_to_caller_fields():
    with pytest.raises(ContractViolation, match="write_answer"):
        check_contract([{"write_answer": {"evidence_score": 2.0}}], skeleton.SKELETON_CONTRACT)
    with pytest.raises(ContractViolation, match="the caller"):
        check_contract([{"score": {"question": "changed"}}], skeleton.SKELETON_CONTRACT)


def test_contract_ignores_nodes_that_return_nothing():
    check_contract([{"score": None}], skeleton.SKELETON_CONTRACT)


def test_loader_reads_title_from_heading():
    doc = source("A1")
    assert doc["title"] == "Solvane Dynamics reports results for the third quarter of 2025"
    assert not doc["text"].startswith("#")
    assert doc["date"] == "2025-11-04"


class _NoReducerState(TypedDict, total=False):
    question: str
    documents: list
    history: Annotated[list[str], operator.add]


def _collectors_without_reducer(parallel: bool):
    def collect_press(state: _NoReducerState) -> dict:
        return {"documents": [source("A1")], "history": ["collect_press: added A1"]}

    def collect_news(state: _NoReducerState) -> dict:
        return {"documents": [source("A2")], "history": ["collect_news: added A2"]}

    builder = StateGraph(_NoReducerState)
    builder.add_node("collect_press", collect_press)
    builder.add_node("collect_news", collect_news)
    if parallel:
        builder.add_edge(START, "collect_press")
        builder.add_edge(START, "collect_news")
        builder.add_edge("collect_press", END)
        builder.add_edge("collect_news", END)
    else:
        builder.add_edge(START, "collect_press")
        builder.add_edge("collect_press", "collect_news")
        builder.add_edge("collect_news", END)
    return builder.compile()


def test_without_reducer_sequential_writes_overwrite_silently():
    result = _collectors_without_reducer(parallel=False).invoke({"question": "q"})
    assert _ids(result["documents"]) == ["A2"]
    assert "collect_press: added A1" in result["history"]


def test_nb02_e02_parallel_writes_without_reducer():
    with pytest.raises(InvalidUpdateError, match="one value per step"):
        _collectors_without_reducer(parallel=True).invoke({"question": "q"})


def test_nb02_e01_forgotten_return_loses_the_update_silently():
    def score_forgetting_return(state: ResearchState) -> None:
        total = sum(doc["authority_weight"] for doc in state["documents"])  # noqa: F841

    builder = StateGraph(ResearchState)
    builder.add_node("collect_press", skeleton.collect_press)
    builder.add_node("score", score_forgetting_return)
    builder.add_edge(START, "collect_press")
    builder.add_edge("collect_press", "score")
    builder.add_edge("score", END)
    result = builder.compile().invoke({"question": skeleton.QUESTION})
    assert "evidence_score" not in result
