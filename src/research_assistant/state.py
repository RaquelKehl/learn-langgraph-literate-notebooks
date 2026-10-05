"""The research assistant's state and its contract (NB 02).

The state is a form with fixed fields that travels from node to node.
Nodes never change it in place: they return only the fields they change,
and LangGraph merges these partial updates. A field with a reducer
(declared with Annotated) merges writes from several nodes; a field
without one accepts a single write per step and is overwritten.

Which node may write which field is a contract. LangGraph does not
enforce it, so check_contract() does.
"""
from __future__ import annotations

import operator
from collections.abc import Iterable
from typing import Annotated, TypedDict

ANY_NODE = "*"


class SourceDoc(TypedDict):
    """One corpus document as it travels in the state."""

    source_id: str
    title: str
    topic: str
    type: str
    publisher: str
    date: str
    authority_weight: float
    based_on: list[str]
    text: str


def merge_documents(existing: list[SourceDoc] | None, new: list[SourceDoc] | None) -> list[SourceDoc]:
    """Reducer for `documents`: union without duplicates, sorted by source_id.

    Sorting makes the result independent of which parallel node finished
    first, so every run produces the same list.
    """
    by_id: dict[str, SourceDoc] = {}
    for doc in [*(existing or []), *(new or [])]:
        by_id.setdefault(doc["source_id"], doc)
    return [by_id[source_id] for source_id in sorted(by_id)]


def merge_claims(existing: dict[str, str | None] | None, new: dict[str, str | None] | None) -> dict[str, str | None]:
    """Reducer for `claims`: keep every claim already read, add new ones.

    A document read again keeps its first claim, so a later round never
    rewrites what an earlier round established. Keys are sorted, so the
    result does not depend on the order in which documents were read.
    """
    merged = dict(new or {})
    merged.update(existing or {})
    return {source_id: merged[source_id] for source_id in sorted(merged)}


class ResearchState(TypedDict, total=False):
    question: str
    query: str  # from NB 04: the search query of rounds 2 and 3
    retrieval_round: int  # from NB 04: absent in round 1
    documents: Annotated[list[SourceDoc], merge_documents]
    claims: Annotated[dict[str, str | None], merge_claims]  # from NB 03: the figure each document states
    evidence_score: float
    contradiction_flag: bool
    draft_answer: str
    review_decision: str  # from NB 06: approve or reject, from a person
    history: Annotated[list[str], operator.add]


class ContractViolation(Exception):
    """A node wrote a state field it does not own."""


def check_contract(updates: Iterable[dict], contract: dict[str, set[str]]) -> None:
    """Check the updates yielded by graph.stream() against a contract.

    `contract` maps each field to the set of nodes allowed to write it;
    ANY_NODE allows every node. A field missing from the contract may only
    be set by the caller.
    """
    for update in updates:
        for node, partial in update.items():
            if node.startswith("__"):  # LangGraph's own entries, such as __interrupt__
                continue
            for field_name in partial or {}:
                writers = contract.get(field_name, set())
                if ANY_NODE not in writers and node not in writers:
                    owners = ", ".join(sorted(writers)) or "the caller"
                    raise ContractViolation(
                        f"node '{node}' wrote '{field_name}', which only {owners} may write"
                    )
