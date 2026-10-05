"""Stage 5 (NB 05): the model judges the evidence, and the rules check it.

Until NB 04 the model only read: one figure per document, or a search query.
Here it is asked to judge the whole evidence for a question, in a fixed JSON
form, so that its verdict can be compared field by field with the rules.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

from research_assistant.evidence import Assessment, origin
from research_assistant.state import SourceDoc

JUDGE_PROMPT = ChatPromptTemplate.from_template(
    "You are assessing evidence for a research question. Read the documents and judge the evidence.\n"
    "Reply with JSON only, in exactly this form:\n"
    '{{"answer": "<the figure you would report, or null>", "contradiction": <true if the documents state '
    'incompatible figures, else false>, "independent_sources": <number of independent sources that support '
    'your answer>, "outdated": [<ids of documents that are outdated>], "sufficient": <true if the evidence is '
    'strong enough to answer with confidence, else false>, "reason": "<one sentence>"}}\n\n'
    "Question: {question}\n\nDocuments:\n{documents}"
)

LISTING_JUDGE_PROMPT = ChatPromptTemplate.from_template(
    "You are assessing evidence for a research question. First list, for every document, the figure it "
    "states in answer to the question. Then judge the evidence.\n"
    "Reply with JSON only, in exactly this form:\n"
    '{{"figures": {{"<document id>": "<figure or null>"}}, "answer": "<the figure you would report, or null>", '
    '"contradiction": <true if any two documents state incompatible figures, else false>, '
    '"independent_sources": <number of independent sources that support your answer; a document based on '
    'another counts once with it>, "outdated": [<ids of documents that are outdated>], "sufficient": <true '
    'if the evidence is strong enough to answer with confidence, else false>, "reason": "<one sentence>"}}\n\n'
    "Question: {question}\n\nDocuments:\n{documents}"
)


@dataclass(frozen=True)
class Verdict:
    answer: str | None
    contradiction: bool
    independent_sources: int
    outdated: list[str]
    sufficient: bool
    reason: str


def format_documents(documents: list[SourceDoc], with_metadata: bool = True) -> str:
    blocks = []
    for doc in documents:
        block = f"[{doc['source_id']}] {doc['title']}\n"
        if with_metadata:
            meta = (
                f"publisher: {doc['publisher']}; type: {doc['type']}; "
                f"date: {doc['date']}; authority: {doc['authority_weight']}"
            )
            if doc["based_on"]:
                meta += f"; based on: {', '.join(doc['based_on'])}"
            block += f"({meta})\n"
        blocks.append(block + doc["text"])
    return "\n\n".join(blocks)


def read_verdict(reply: str) -> Verdict:
    text = reply.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    data = json.loads(text)
    answer = data.get("answer")
    return Verdict(
        answer=None if answer in (None, "null") else str(answer),
        contradiction=bool(data["contradiction"]),
        independent_sources=int(data["independent_sources"]),
        outdated=sorted(data.get("outdated") or []),
        sufficient=bool(data["sufficient"]),
        reason=str(data.get("reason", "")),
    )


def judge(
    llm: BaseChatModel,
    question: str,
    documents: list[SourceDoc],
    with_metadata: bool = True,
    prompt: ChatPromptTemplate = JUDGE_PROMPT,
) -> Verdict:
    messages = prompt.invoke({"question": question, "documents": format_documents(documents, with_metadata)})
    return read_verdict(llm.invoke(messages).content)


def _number(figure: str | None) -> float | None:
    match = re.search(r"\d+(?:\.\d+)?", figure or "")
    return float(match.group()) if match else None


def origins_stating(figure: str | None, documents: list[SourceDoc], claims: dict[str, str | None]) -> int:
    """How many independent origins state this figure, whatever their authority."""
    by_id = {doc["source_id"]: doc for doc in documents}
    target = _number(figure)
    ids = [sid for sid, claim in claims.items() if sid in by_id and target is not None and _number(claim) == target]
    return len({origin(sid, by_id) for sid in ids})


def compare(
    verdict: Verdict, assessment: Assessment, documents: list[SourceDoc], claims: dict[str, str | None]
) -> list[tuple[str, object, object, bool]]:
    """Field by field: (field, model, rules, agree)."""
    outdated = sorted(sid for sid, reason in assessment.disregarded.items() if reason.startswith("outdated"))
    origins = origins_stating(verdict.answer, documents, claims)
    rows = [
        ("answer", verdict.answer, assessment.answer, _number(verdict.answer) == _number(assessment.answer)),
        ("contradiction", verdict.contradiction, assessment.contradiction_flag, verdict.contradiction == assessment.contradiction_flag),
        ("independent sources for that answer", verdict.independent_sources, origins, verdict.independent_sources == origins),
        ("outdated", verdict.outdated, outdated, verdict.outdated == outdated),
        ("sufficient", verdict.sufficient, assessment.sufficient, verdict.sufficient == assessment.sufficient),
    ]
    return rows
