"""Stage 2 (NB 02): the assistant's skeleton under a state contract.

Two collectors run in parallel and add documents, a scorer sets the
evidence fields, and a writer drafts the answer. Collecting and scoring
are stand-ins here: the collectors add fixed documents, and the score is
a plain sum of authority weights. NB 03 replaces both with real retrieval
and the evidence rules of ADR 0007.
"""
from __future__ import annotations

from functools import cache

from langgraph.graph import END, START, StateGraph

from research_assistant.hello import QUESTION
from research_assistant.state import ANY_NODE, ResearchState, SourceDoc
from research_assistant.tools import load_corpus, to_source_doc

__all__ = ["QUESTION", "SKELETON_CONTRACT", "build_skeleton_graph", "source"]

SKELETON_CONTRACT: dict[str, set[str]] = {
    "documents": {"collect_press", "collect_news"},
    "evidence_score": {"score"},
    "contradiction_flag": {"score"},
    "draft_answer": {"write_answer"},
    "history": {ANY_NODE},
}


@cache
def _corpus() -> dict[str, SourceDoc]:
    return {doc.source_id: to_source_doc(doc) for doc in load_corpus()}


def source(source_id: str) -> SourceDoc:
    return _corpus()[source_id]


def collect_press(state: ResearchState) -> dict:
    return {"documents": [source("A1")], "history": ["collect_press: added A1"]}


def collect_news(state: ResearchState) -> dict:
    return {"documents": [source("A2")], "history": ["collect_news: added A2"]}


def score(state: ResearchState) -> dict:
    documents = state["documents"]
    total = round(sum(doc["authority_weight"] for doc in documents), 2)
    return {
        "evidence_score": total,
        "contradiction_flag": False,
        "history": [f"score: {len(documents)} documents, evidence score {total}"],
    }


def write_answer(state: ResearchState) -> dict:
    ids = ", ".join(doc["source_id"] for doc in state["documents"])
    return {
        "draft_answer": (
            f"{len(state['documents'])} documents collected ({ids}), "
            f"evidence score {state['evidence_score']}."
        ),
        "history": ["write_answer: draft written"],
    }


def build_skeleton_graph():
    builder = StateGraph(ResearchState)
    builder.add_node("collect_press", collect_press)
    builder.add_node("collect_news", collect_news)
    builder.add_node("score", score)
    builder.add_node("write_answer", write_answer)
    builder.add_edge(START, "collect_press")
    builder.add_edge(START, "collect_news")
    builder.add_edge(["collect_press", "collect_news"], "score")
    builder.add_edge("score", "write_answer")
    builder.add_edge("write_answer", END)
    return builder.compile()
