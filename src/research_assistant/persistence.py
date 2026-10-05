"""Stage 6 (NB 06): checkpoints and a pause for human review.

The graph of NB 04 gains a review step. When the evidence stays uncertain,
the run saves its state, pauses with interrupt() and waits for a person to
approve or reject the limited answer. A checkpointer keeps the state while
the run waits, in memory or in a local SQLite file, so the run can continue
exactly where it stopped, even after a restart.

interrupt() fires on exactly two triggers (ADR 0007):
1. the quality gate still fails after the last search round;
2. two qualifying sources contradict each other on a fact. No corpus topic
   produces this, so CONSTRUCTED_REPORT builds the case openly.
"""
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from research_assistant.assistant import collect_primary, collect_secondary, make_score, write_answer
from research_assistant.evidence import EVIDENCE_THRESHOLD, assess, format_figure, parse_figure
from research_assistant.loop import LOOP_CONTRACT, MAX_ROUNDS, limitation_text, make_refine_query
from research_assistant.state import ResearchState, SourceDoc

DECISIONS = ("approve", "reject")

REVIEW_CONTRACT: dict[str, set[str]] = {
    **LOOP_CONTRACT,
    "review_decision": {"human_review"},
    "draft_answer": {"write_answer", "publish_reviewed", "withhold_answer"},
}

CONSTRUCTED_REPORT = SourceDoc(
    source_id="X1",
    title="Solvane Dynamics revenue lower than first reported, news wire says",
    topic="topic_a_quarterly_earnings",
    type="news_article",
    publisher="Lakeside Business Wire",
    date="2025-11-05",
    authority_weight=0.7,
    based_on=[],
    text=(
        "Solvane Dynamics AG (fictional) reported revenue of CHF 320 million for the third quarter "
        "of 2025, according to a breakdown the company circulated to analysts after its results "
        "call on 4 November 2025. The figure excludes a one-off licence payment that the company's "
        "own release included. Lakeside Business Wire (fictional) has asked the company to confirm "
        "which figure it regards as its reported revenue."
    ),
)


def conflicting_figures(state: ResearchState) -> str:
    """The qualifying figures that contradict each other, with their sources."""
    result = assess(state["documents"], state["claims"])
    ids = {doc["source_id"] for doc in state["documents"]}
    by_figure: dict[str, list[str]] = {}
    for sid, figure in state["claims"].items():
        if figure is not None and sid in ids and sid not in result.disregarded:
            by_figure.setdefault(format_figure(parse_figure(figure)), []).append(sid)
    return " against ".join(f"{figure} ({', '.join(sorted(s))})" for figure, s in sorted(by_figure.items()))


def review_trigger(state: ResearchState) -> str:
    if assess(state["documents"], state["claims"]).unresolved:
        return f"qualifying sources contradict each other: {conflicting_figures(state)}"
    return f"the quality gate is not passed after {state.get('retrieval_round', 1)} of {MAX_ROUNDS} search rounds"


def route_with_review(state: ResearchState) -> str:
    """Read the evidence; never write. Two triggers lead to a human review."""
    if state["evidence_score"] >= EVIDENCE_THRESHOLD:
        return "answer"
    if assess(state["documents"], state["claims"]).unresolved:
        return "review"  # trigger 2: another search will not settle credible disagreement
    if state.get("retrieval_round", 1) < MAX_ROUNDS:
        return "search_again"
    return "review"  # trigger 1


def human_review(state: ResearchState) -> dict:
    trigger = review_trigger(state)
    reply = interrupt({"trigger": trigger, "draft": limitation_text(state), "options": list(DECISIONS)})
    decision = reply.get("decision") if isinstance(reply, dict) else reply
    if decision not in DECISIONS:
        raise ValueError(f"review decision must be one of {DECISIONS}, got {decision!r}")
    note = reply.get("note", "") if isinstance(reply, dict) else ""
    return {
        "review_decision": decision,
        "history": [f"human_review: {trigger}; reviewer decided {decision}" + (f" ({note})" if note else "")],
    }


def route_after_review(state: ResearchState) -> str:
    return "publish" if state["review_decision"] == "approve" else "withhold"


def publish_reviewed(state: ResearchState) -> dict:
    return {
        "draft_answer": f"Approved after human review. {limitation_text(state)}",
        "history": ["publish_reviewed: limited answer published"],
    }


def withhold_answer(state: ResearchState) -> dict:
    return {
        "draft_answer": (
            f"Withheld after human review: the reviewer did not approve an answer, because "
            f"{review_trigger(state)}."
        ),
        "history": ["withhold_answer: no answer published"],
    }


def build_review_graph(llm: BaseChatModel, checkpointer):
    builder = StateGraph(ResearchState)
    builder.add_node("collect_primary", collect_primary)
    builder.add_node("collect_secondary", collect_secondary)
    builder.add_node("score", make_score(llm))
    builder.add_node("refine_query", make_refine_query(llm))
    builder.add_node("write_answer", write_answer)
    builder.add_node("human_review", human_review)
    builder.add_node("publish_reviewed", publish_reviewed)
    builder.add_node("withhold_answer", withhold_answer)
    builder.add_edge(START, "collect_primary")
    builder.add_edge(START, "collect_secondary")
    builder.add_edge(["collect_primary", "collect_secondary"], "score")
    builder.add_conditional_edges(
        "score",
        route_with_review,
        {"answer": "write_answer", "search_again": "refine_query", "review": "human_review"},
    )
    builder.add_edge("refine_query", "collect_primary")
    builder.add_edge("refine_query", "collect_secondary")
    builder.add_conditional_edges("human_review", route_after_review, {"publish": "publish_reviewed", "withhold": "withhold_answer"})
    builder.add_edge("write_answer", END)
    builder.add_edge("publish_reviewed", END)
    builder.add_edge("withhold_answer", END)
    return builder.compile(checkpointer=checkpointer)
