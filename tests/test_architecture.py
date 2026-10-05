"""The architecture diagram (docs/architecture.svg) must not drift from the code.

The test reads the diagram's own text and compares it with the real graph, the
state schema, the router and the constants the diagram prints. If the code
changes and the diagram does not (or the other way round), a test fails.
"""
import re
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from research_assistant import assistant, evidence, persistence
from research_assistant.loop import MAX_ROUNDS
from research_assistant.models import get_chat_model
from research_assistant.retrieval import RELEVANCE_CUTOFF
from research_assistant.state import ResearchState
from research_assistant.tools import load_corpus

SVG = Path(__file__).resolve().parents[1] / "docs" / "architecture.svg"
SVG_NS = "{http://www.w3.org/2000/svg}"
FUNCTIONS = {
    "extract_claim": assistant.extract_claim,
    "assess": evidence.assess,
    "route_with_review": persistence.route_with_review,
}


def _texts(path=None):
    root = ET.parse(path or SVG).getroot()
    result = []
    for element in root.iter(SVG_NS + "text"):
        result.append((element.get("id", ""), "mono" in (element.get("font-family") or ""), "".join(element.itertext()).strip()))
    return result


def _real_nodes():
    graph = persistence.build_review_graph(get_chat_model("fake"), InMemorySaver()).get_graph()
    return set(graph.nodes) - {"__start__", "__end__"}


def test_every_graph_node_appears_in_the_diagram():
    texts = [t for _, _, t in _texts()]
    missing = sorted(n for n in _real_nodes() if not any(t == n or t.endswith(": " + n) for t in texts))
    assert not missing, f"graph nodes missing from the diagram: {missing}"


def test_every_code_name_in_the_diagram_exists_in_the_code():
    allowed = _real_nodes() | set(FUNCTIONS) | set(ResearchState.__annotations__)
    code_names = {t for _, mono, t in _texts() if mono and not t.startswith(("notebook", "graph node:"))}
    unknown = sorted(code_names - allowed)
    assert not unknown, f"names in the diagram that the code does not have: {unknown}"
    assert all(callable(f) for f in FUNCTIONS.values())


def test_state_chips_are_exactly_the_state_schema():
    chips = {t for i, _, t in _texts() if i.startswith("cht_")}
    assert chips == set(ResearchState.__annotations__)


def test_router_labels_and_decisions_are_the_real_ones():
    texts = {t for _, _, t in _texts()}
    states = [{"evidence_score": 1.6}, {"evidence_score": 0.85}, {"evidence_score": 0.85, "retrieval_round": MAX_ROUNDS}]
    for state in states:
        # route_with_review reads documents and claims only when the score is below the gate
        state = {**state, "documents": [], "claims": {}}
        assert persistence.route_with_review(state).replace("_", " ") in texts
    for decision in persistence.DECISIONS:
        assert decision in texts


def test_numbers_printed_in_the_diagram_match_the_code():
    texts = {t for _, _, t in _texts()}
    expected = {
        f"cut-off: {RELEVANCE_CUTOFF:.0%} of best",
        f"{len(load_corpus())} fictional docs",
        f"gate: {evidence.EVIDENCE_THRESHOLD}",
        f"max {MAX_ROUNDS} rounds",
        f"round 1 of {MAX_ROUNDS}",
        f"round {MAX_ROUNDS} of {MAX_ROUNDS}",
    }
    assert expected <= texts, f"not in the diagram: {sorted(expected - texts)}"


def test_svg_is_safe_for_a_github_readme():
    raw = SVG.read_text(encoding="utf-8")
    assert "<script" not in raw, "GitHub does not run scripts in SVG images"
    assert not re.search(r'(href|src)\s*=\s*"(https?:|//)', raw), "external references are blocked in SVG images"
    assert "<title" in raw and "<desc" in raw, "the diagram needs an accessible title and description"
