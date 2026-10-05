"""Stage 6 (NB 06): checkpoints, the two review triggers, and resuming."""
import sqlite3
from typing import TypedDict

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from research_assistant import persistence
from research_assistant.evidence import CANONICAL_QUESTIONS
from research_assistant.models import get_chat_model
from research_assistant.state import check_contract

LLM = get_chat_model("fake", fixture=("nb03_claims.yaml", "nb04_queries.yaml", "nb06_constructed.yaml"))


def _config(thread_id):
    return {"configurable": {"thread_id": thread_id}}


@pytest.fixture
def graph():
    return persistence.build_review_graph(LLM, InMemorySaver())


@pytest.mark.parametrize("topic", "abde")
def test_answered_topics_never_pause(graph, topic):
    result = graph.invoke({"question": CANONICAL_QUESTIONS[topic]}, _config(topic))
    assert "__interrupt__" not in result and "review_decision" not in result


def test_trigger_one_pauses_topic_c_after_round_three(graph):
    result = graph.invoke({"question": CANONICAL_QUESTIONS["c"]}, _config("c"))
    assert result["retrieval_round"] == 3
    assert graph.get_state(_config("c")).next == ("human_review",)
    assert result["__interrupt__"][0].value["trigger"].startswith("the quality gate is not passed after 3 of 3")


def test_trigger_two_pauses_the_constructed_case_in_round_one(graph):
    start = {"question": CANONICAL_QUESTIONS["a"], "documents": [persistence.CONSTRUCTED_REPORT]}
    result = graph.invoke(start, _config("x"))
    assert result.get("retrieval_round", 1) == 1
    assert result["__interrupt__"][0].value["trigger"] == (
        "qualifying sources contradict each other: CHF 320 million (X1) against CHF 342 million (A1, A2)"
    )


def test_approve_and_reject_take_different_routes(graph):
    for thread, decision in (("approve", "approve"), ("reject", "reject")):
        graph.invoke({"question": CANONICAL_QUESTIONS["c"]}, _config(thread))
        final = graph.invoke(Command(resume={"decision": decision}), _config(thread))
        assert final["review_decision"] == decision
    approved = graph.get_state(_config("approve")).values["draft_answer"]
    rejected = graph.get_state(_config("reject")).values["draft_answer"]
    assert approved.startswith("Approved after human review. Limited answer after 3 of 3 search rounds")
    assert rejected.startswith("Withheld after human review")


def test_contract_holds_through_pause_and_resume(graph):
    check_contract(graph.stream({"question": CANONICAL_QUESTIONS["c"]}, _config("k")), persistence.REVIEW_CONTRACT)
    check_contract(graph.stream(Command(resume={"decision": "reject"}), _config("k")), persistence.REVIEW_CONTRACT)


def test_a_restart_resumes_from_the_sqlite_file(tmp_path):
    database = tmp_path / "checkpoints.sqlite"
    first = sqlite3.connect(database, check_same_thread=False)
    persistence.build_review_graph(LLM, SqliteSaver(first)).invoke(
        {"question": CANONICAL_QUESTIONS["c"]}, _config("c")
    )
    first.close()
    second = sqlite3.connect(database, check_same_thread=False)
    graph = persistence.build_review_graph(LLM, SqliteSaver(second))
    assert graph.get_state(_config("c")).next == ("human_review",)
    final = graph.invoke(Command(resume={"decision": "approve"}), _config("c"))
    second.close()
    assert final["draft_answer"].startswith("Approved after human review")


def test_an_invalid_decision_is_refused(graph):
    graph.invoke({"question": CANONICAL_QUESTIONS["c"]}, _config("bad"))
    with pytest.raises(ValueError, match="approve"):
        graph.invoke(Command(resume={"decision": "yes"}), _config("bad"))


class _S(TypedDict, total=False):
    question: str
    decision: str


def _pausing_graph(checkpointer):
    builder = StateGraph(_S)
    builder.add_node("review", lambda s: {"decision": interrupt("approve?")})
    builder.add_edge(START, "review")
    builder.add_edge("review", END)
    return builder.compile(checkpointer=checkpointer)


def test_nb06_e01_pausing_without_a_checkpointer_cannot_be_resumed():
    graph = _pausing_graph(None)
    assert "__interrupt__" in graph.invoke({"question": "q"})  # the pause looks normal
    with pytest.raises(RuntimeError, match="without checkpointer"):
        graph.invoke(Command(resume="approve"))


def test_nb06_e02_resuming_on_another_thread_starts_from_nothing(graph):
    graph.invoke({"question": CANONICAL_QUESTIONS["c"]}, _config("c-review"))
    assert graph.get_state(_config("c-reveiw")).values == {}
    with pytest.raises(KeyError, match="question"):
        graph.invoke(Command(resume={"decision": "approve"}), _config("c-reveiw"))
