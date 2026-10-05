"""Stage 1 (NB 01): one question, one document, one answer, built twice.

The same step is composed once as an LCEL chain and once as a LangGraph
StateGraph. Both use the same prompt and the same model, so they must give
the same answer; what differs is how the step is put together.
"""
from __future__ import annotations

from typing import TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph

DOCUMENT = (
    "Solvane Dynamics AG reported revenue of CHF 342 million for the third quarter "
    "of 2025, an increase of 14.8% compared with the same quarter of the previous year."
)
QUESTION = "What revenue did Solvane Dynamics report for the third quarter of 2025?"
UNANSWERABLE_QUESTION = (
    "What net profit did Solvane Dynamics report for the third quarter of 2025?"
)
NOT_IN_DOCUMENT = "The document does not say."

ANSWER_PROMPT = ChatPromptTemplate.from_template(
    "Answer the question in one sentence, using only the document below. "
    "If the document does not contain the answer, reply exactly: "
    '"' + NOT_IN_DOCUMENT + '"'
    "\n\nDocument: {document}\n\nQuestion: {question}"
)


class HelloState(TypedDict, total=False):
    question: str
    draft_answer: str


def build_chain(llm: BaseChatModel):
    """Version A: prompt, model and parser joined by the pipe operator."""
    return ANSWER_PROMPT | llm | StrOutputParser()


def build_graph(llm: BaseChatModel):
    """Version B: the same step as one node that reads and writes a state."""

    def answer(state: HelloState) -> dict:
        messages = ANSWER_PROMPT.invoke(
            {"document": DOCUMENT, "question": state["question"]}
        )
        reply = llm.invoke(messages)
        return {"draft_answer": reply.content}

    builder = StateGraph(HelloState)
    builder.add_node("answer", answer)
    builder.add_edge(START, "answer")
    builder.add_edge("answer", END)
    return builder.compile()
