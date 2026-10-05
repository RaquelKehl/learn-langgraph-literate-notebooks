"""Stage 3 (NB 03): real retrieval and the evidence rules in the skeleton.

The topology of NB 02 stays: two collectors in parallel, then scoring,
then writing. The collectors now search the corpus, one for primary
sources (original institutional or first-party material) and one for
secondary sources (press, research, commentary, forums). The split is a
retrieval partition for this corpus, not a general taxonomy of sources. The scorer
asks the model for each document's claim and applies the evidence rules.
"""
from __future__ import annotations

from functools import cache

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph

from research_assistant.evidence import AUTHORITY_FLOOR, EVIDENCE_THRESHOLD, assess, read_claim
from research_assistant.retrieval import retrieve, word_weights
from research_assistant.state import ANY_NODE, ResearchState, SourceDoc
from research_assistant.tools import load_corpus, to_source_doc

PRIMARY_TYPES = frozenset(
    {"press_release", "regulatory_circular", "investor_presentation_summary", "industry_report", "consumer_study"}
)

CLAIM_PROMPT = ChatPromptTemplate.from_template(
    "Read the document and find the figure it states in answer to the question. "
    'Reply with JSON only, in exactly this form: {{"figure": "<the figure as written in the document>"}}. '
    'If the document does not state such a figure, reply {{"figure": null}}.\n\n'
    "Question: {question}\n\nDocument: {document}"
)

RESEARCH_CONTRACT: dict[str, set[str]] = {
    "documents": {"collect_primary", "collect_secondary"},
    "claims": {"score"},
    "evidence_score": {"score"},
    "contradiction_flag": {"score"},
    "draft_answer": {"write_answer"},
    "history": {ANY_NODE},
}


@cache
def corpus() -> tuple[SourceDoc, ...]:
    return tuple(to_source_doc(doc) for doc in load_corpus())


@cache
def weights() -> dict[str, float]:
    return word_weights(corpus())


def _collect(question: str, primary: bool) -> list[SourceDoc]:
    found = retrieve(question, corpus(), weights())
    return [doc for doc in found if (doc["type"] in PRIMARY_TYPES) == primary]


def _search_text(state: ResearchState) -> str:
    """Round 1 searches with the question; later rounds with the new query (NB 04)."""
    return state.get("query") or state["question"]


def _label(node: str, state: ResearchState) -> str:
    return f"{node} (round {state['retrieval_round']})" if "retrieval_round" in state else node


def collect_primary(state: ResearchState) -> dict:
    found = _collect(_search_text(state), primary=True)
    ids = ", ".join(doc["source_id"] for doc in found) or "nothing"
    return {"documents": found, "history": [f"{_label('collect_primary', state)}: found {ids}"]}


def collect_secondary(state: ResearchState) -> dict:
    found = _collect(_search_text(state), primary=False)
    ids = ", ".join(doc["source_id"] for doc in found) or "nothing"
    return {"documents": found, "history": [f"{_label('collect_secondary', state)}: found {ids}"]}


def extract_claim(llm: BaseChatModel, question: str, doc: SourceDoc) -> str | None:
    messages = CLAIM_PROMPT.invoke(
        {"question": question, "document": f"{doc['title']}\n\n{doc['text']}"}
    )
    return read_claim(llm.invoke(messages).content)


def write_answer_text(state: ResearchState) -> str:
    """The answer, written from the state by the same rules the scorer used."""
    result = assess(state["documents"], state["claims"])
    notes = [f"{sid} disregarded: {reason}." for sid, reason in sorted(result.disregarded.items())]
    rounds = state.get("retrieval_round")
    insufficient = f"Evidence insufficient after {rounds} search rounds" if rounds else "Evidence insufficient"
    if result.sufficient:
        head = f"{result.answer} (sources: {', '.join(result.supporting)}; evidence score {result.evidence_score:g})."
        if rounds:
            first_round = {doc["source_id"] for doc in retrieve(state["question"], corpus(), weights())}
            later = [sid for sid in result.supporting if sid not in first_round]
            found = f" found {', '.join(later)}" if later else " found further evidence"
            head += (
                f" The quality gate was passed in search round {rounds}, "
                f"after a rephrased search{found}."
            )
    elif result.unresolved:
        head = "No confident answer: qualifying sources contradict each other."
    elif result.answer:
        head = (
            f"{insufficient}: {result.answer} rests on {', '.join(result.supporting)} only "
            f"(evidence score {result.evidence_score:g}, threshold {EVIDENCE_THRESHOLD:.1f})."
        )
    else:
        head = f"{insufficient}: no source at or above the authority floor of {AUTHORITY_FLOOR:g} states a figure."
    return " ".join([head, *notes])


def make_score(llm: BaseChatModel):
    """The scoring node: read the claims of documents not yet read, then apply the rules."""

    def score(state: ResearchState) -> dict:
        known = state.get("claims") or {}
        new_claims = {
            doc["source_id"]: extract_claim(llm, state["question"], doc)
            for doc in state["documents"]
            if doc["source_id"] not in known
        }
        result = assess(state["documents"], {**known, **new_claims})
        return {
            "claims": new_claims,
            "evidence_score": result.evidence_score,
            "contradiction_flag": result.contradiction_flag,
            "history": [
                f"{_label('score', state)}: evidence score {result.evidence_score:g}, "
                f"contradiction {result.contradiction_flag}, gate passed {result.sufficient}"
            ],
        }

    return score


def write_answer(state: ResearchState) -> dict:
    return {"draft_answer": write_answer_text(state), "history": ["write_answer: draft written"]}


def build_research_graph(llm: BaseChatModel):
    builder = StateGraph(ResearchState)
    builder.add_node("collect_primary", collect_primary)
    builder.add_node("collect_secondary", collect_secondary)
    builder.add_node("score", make_score(llm))
    builder.add_node("write_answer", write_answer)
    builder.add_edge(START, "collect_primary")
    builder.add_edge(START, "collect_secondary")
    builder.add_edge(["collect_primary", "collect_secondary"], "score")
    builder.add_edge("score", "write_answer")
    builder.add_edge("write_answer", END)
    return builder.compile()
