"""Stage 1 (NB 01): chain and graph must agree, and the mistakes must fail
with the documented exception types."""
from typing import TypedDict

import pytest
from langchain_core.prompts import ChatPromptTemplate
from langgraph.errors import InvalidUpdateError
from langgraph.graph import END, START, StateGraph

from research_assistant import hello
from research_assistant.models import get_chat_model

RECORDED_ANSWER = (
    "Solvane Dynamics reported revenue of CHF 342 million for the third quarter of 2025."
)


@pytest.fixture
def llm():
    return get_chat_model("fake", fixture="nb01_hello.yaml")


def test_chain_and_graph_give_the_same_answer(llm):
    chain_answer = hello.build_chain(llm).invoke(
        {"document": hello.DOCUMENT, "question": hello.QUESTION}
    )
    graph_result = hello.build_graph(llm).invoke({"question": hello.QUESTION})
    assert chain_answer == graph_result["draft_answer"] == RECORDED_ANSWER


def test_missing_answer_uses_the_fixed_reply(llm):
    result = hello.build_graph(llm).invoke({"question": hello.UNANSWERABLE_QUESTION})
    assert result["draft_answer"] == hello.NOT_IN_DOCUMENT


def test_graph_shape(llm):
    graph = hello.build_graph(llm).get_graph()
    assert set(graph.nodes) == {"__start__", "answer", "__end__"}
    assert {(e.source, e.target) for e in graph.edges} == {
        ("__start__", "answer"),
        ("answer", "__end__"),
    }


def test_first_prompt_answers_missing_information_in_free_form(llm):
    # The prompt log's v1: the recorded reply explains instead of signalling.
    v1 = ChatPromptTemplate.from_template(
        "Answer the question.\n\nDocument: {document}\n\nQuestion: {question}"
    )
    reply = (v1 | llm).invoke(
        {"document": hello.DOCUMENT, "question": hello.UNANSWERABLE_QUESTION}
    )
    assert reply.content != hello.NOT_IN_DOCUMENT
    assert "cannot be determined" in reply.content


class _State(TypedDict, total=False):
    question: str
    draft_answer: str


def test_nb01_e01_compile_without_entry_edge():
    builder = StateGraph(_State)
    builder.add_node("answer", lambda s: {"draft_answer": "x"})
    builder.add_edge("answer", END)
    with pytest.raises(ValueError, match="entrypoint"):
        builder.compile()


def test_nb01_e02_node_returns_a_string():
    builder = StateGraph(_State)
    builder.add_node("answer", lambda s: "CHF 342 million")
    builder.add_edge(START, "answer")
    builder.add_edge("answer", END)
    with pytest.raises(InvalidUpdateError, match="Expected dict"):
        builder.compile().invoke({"question": "q"})


def test_nb01_e03_prompt_variable_missing(llm):
    with pytest.raises(KeyError, match="missing variables"):
        hello.build_chain(llm).invoke({"question": hello.QUESTION})
