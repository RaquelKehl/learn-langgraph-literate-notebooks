"""Stage 4 (NB 04): a router and a bounded search loop.

After scoring, a deterministic router reads the evidence score and the round
counter and picks one of three routes: answer, search again with a new
query, or stop with a stated limitation. The quality gate stays fixed; only
the search query changes from round to round (ADR 0007).
"""
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph

from research_assistant.assistant import (
    RESEARCH_CONTRACT,
    collect_primary,
    collect_secondary,
    make_score,
    write_answer,
)
from research_assistant.evidence import AUTHORITY_FLOOR, EVIDENCE_THRESHOLD, assess
from research_assistant.state import ResearchState

MAX_ROUNDS = 3  # P5: the business stop condition

SYNONYM_PROMPT = ChatPromptTemplate.from_template(
    "Write a new search query for the question below. Use different words: replace the "
    "question's key terms with synonyms and the technical terms used in the field, so that "
    "documents that describe the same thing in other words are found too. Keep any names. "
    "Reply with the query only, on one line.\n\nQuestion: {question}"
)
BROADER_PROMPT = ChatPromptTemplate.from_template(
    "Write a broader search query about the general subject of the question below. Leave out "
    "details such as figures, dates and the exact measure asked for. Keep any names. "
    "Reply with the query only, on one line.\n\nQuestion: {question}"
)
QUERY_PROMPTS = {2: SYNONYM_PROMPT, 3: BROADER_PROMPT}

LOOP_CONTRACT: dict[str, set[str]] = {
    **RESEARCH_CONTRACT,
    "query": {"refine_query"},
    "retrieval_round": {"refine_query"},
    "draft_answer": {"write_answer", "write_limitation"},
}


def clean_query(reply: str) -> str:
    """The first non-empty line of the reply, without surrounding quotes."""
    line = next((line for line in reply.strip().splitlines() if line.strip()), "")
    return line.strip().strip('"').strip()


def route(state: ResearchState) -> str:
    """Read the evidence score and the round counter; never write anything."""
    if state["evidence_score"] >= EVIDENCE_THRESHOLD:
        return "answer"
    if state.get("retrieval_round", 1) < MAX_ROUNDS:
        return "search_again"
    return "limit_answer"


def make_refine_query(llm: BaseChatModel):
    def refine_query(state: ResearchState) -> dict:
        next_round = state.get("retrieval_round", 1) + 1
        reply = llm.invoke(QUERY_PROMPTS[next_round].invoke({"question": state["question"]})).content
        query = clean_query(reply)
        return {
            "query": query,
            "retrieval_round": next_round,
            "history": [f'refine_query: round {next_round} searches for "{query}"'],
        }

    return refine_query


def limitation_text(state: ResearchState) -> str:
    result = assess(state["documents"], state["claims"])
    rounds = state.get("retrieval_round", 1)
    if result.unresolved:
        why = "qualifying sources contradict each other"
    elif result.answer:
        why = (
            f"{result.answer} rests on {', '.join(result.supporting)} only "
            f"(evidence score {result.evidence_score:g}, threshold {EVIDENCE_THRESHOLD:.1f})"
        )
    else:
        why = f"no source at or above the authority floor of {AUTHORITY_FLOOR:g} states a figure"
    found = ", ".join(doc["source_id"] for doc in state["documents"]) or "none"
    notes = [f"{sid} disregarded: {reason}." for sid, reason in sorted(result.disregarded.items())]
    head = (
        f"Limited answer after {rounds} of {MAX_ROUNDS} search rounds: {why}, so the quality gate "
        f"is not passed. Documents found: {found}. No further search will run."
    )
    return " ".join([head, *notes])


def write_limitation(state: ResearchState) -> dict:
    return {"draft_answer": limitation_text(state), "history": ["write_limitation: limited answer written"]}


def build_loop_graph(llm: BaseChatModel):
    builder = StateGraph(ResearchState)
    builder.add_node("collect_primary", collect_primary)
    builder.add_node("collect_secondary", collect_secondary)
    builder.add_node("score", make_score(llm))
    builder.add_node("refine_query", make_refine_query(llm))
    builder.add_node("write_answer", write_answer)
    builder.add_node("write_limitation", write_limitation)
    builder.add_edge(START, "collect_primary")
    builder.add_edge(START, "collect_secondary")
    builder.add_edge(["collect_primary", "collect_secondary"], "score")
    builder.add_conditional_edges(
        "score",
        route,
        {"answer": "write_answer", "search_again": "refine_query", "limit_answer": "write_limitation"},
    )
    builder.add_edge("refine_query", "collect_primary")
    builder.add_edge("refine_query", "collect_secondary")
    builder.add_edge("write_answer", END)
    builder.add_edge("write_limitation", END)
    return builder.compile()
