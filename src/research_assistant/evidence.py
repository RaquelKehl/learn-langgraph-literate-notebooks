"""The evidence rules (NB 03, ADR 0007).

A model reads each document and reports the figure it states in answer to
the question (a "claim"). Everything after that is plain, deterministic
Python: which claims count, whether they contradict each other, and whether
the evidence passes the quality gate.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field

from research_assistant.state import SourceDoc

AUTHORITY_FLOOR = 0.5  # P1
EVIDENCE_THRESHOLD = 1.0  # P2: summed authority of independent qualifying sources
OUTDATED_AFTER = dt.timedelta(days=365)  # P4: a newer source at least 12 months younger

CANONICAL_QUESTIONS = {
    "a": "What revenue did Solvane Dynamics report for the third quarter of 2025?",
    "b": "What is the implied transaction value of the merger between Talvero Bank and Nordquist Privatbank?",
    "c": "What share of client crypto assets must be kept in cold storage under the new AMSA custody rules?",
    "d": "What is Brunnhof Versicherungen's current dividend payout target?",
    "e": "What is the average annual fee of robo-advisory platforms in Switzerland in 2025?",
}

_SCALES = {"thousand": 1e3, "million": 1e6, "billion": 1e9}


def read_claim(reply: str) -> str | None:
    """The figure from the model's JSON reply, or None if it states none."""
    text = reply.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    figure = json.loads(text)["figure"]
    return str(figure) if figure is not None else None


def parse_figure(figure: str) -> tuple[float, str]:
    """A comparable (value, unit) pair: "CHF 1.2 billion" -> (1.2e9, "CHF")."""
    number = re.search(r"\d+(?:[.,]\d+)?", figure)
    if number is None:
        raise ValueError(f"no number in figure {figure!r}")
    value = float(number.group().replace(",", "."))
    if "%" in figure:
        return value, "%"
    for word, scale in _SCALES.items():
        if word in figure.lower():
            value *= scale
            break
    currency = re.search(r"\b[A-Z]{3}\b", figure)
    return value, currency.group() if currency else ""


def format_figure(parsed: tuple[float, str]) -> str:
    value, unit = parsed
    if unit == "%":
        return f"{value:g}%"
    for word, scale in reversed(_SCALES.items()):
        if value >= scale:
            return f"{unit} {value / scale:g} {word}".strip()
    return f"{unit} {value:g}".strip()


def origin(doc_id: str, documents: dict[str, SourceDoc]) -> str:
    """Follow `based_on` back to the document a copy ultimately rests on."""
    seen = {doc_id}
    current = doc_id
    while documents.get(current, {}).get("based_on"):
        current = documents[current]["based_on"][0]
        if current in seen:
            break
        seen.add(current)
    return current


@dataclass(frozen=True)
class Assessment:
    evidence_score: float
    contradiction_flag: bool
    answer: str | None
    supporting: list[str]
    disregarded: dict[str, str] = field(default_factory=dict)
    unresolved: bool = False

    @property
    def contradiction_resolved(self) -> bool:
        """A contradiction exists, and the rules still leave one supported figure."""
        return self.contradiction_flag and self.answer is not None

    @property
    def sufficient(self) -> bool:
        """P2: at least two independent qualifying sources AND summed authority >= 1.0."""
        return len(self.supporting) >= 2 and self.evidence_score >= EVIDENCE_THRESHOLD


def assess(documents: list[SourceDoc], claims: dict[str, str | None]) -> Assessment:
    by_id = {doc["source_id"]: doc for doc in documents}
    stated = {sid: parse_figure(fig) for sid, fig in claims.items() if fig is not None and sid in by_id}
    disregarded = {sid: "states no figure" for sid in by_id if sid not in stated}

    dates = {sid: dt.date.fromisoformat(by_id[sid]["date"]) for sid in stated}
    for sid in stated:
        newer = [other for other in stated if dates[other] - dates[sid] >= OUTDATED_AFTER]
        if newer:
            # name the most authoritative newer source, the latest among equals
            successor = max(newer, key=lambda other: (by_id[other]["authority_weight"], dates[other]))
            disregarded[sid] = f"outdated: superseded by {successor} ({dates[successor].isoformat()})"
    for sid in stated:
        weight = by_id[sid]["authority_weight"]
        if sid not in disregarded and weight < AUTHORITY_FLOOR:
            disregarded[sid] = f"below the authority floor ({weight:g} < {AUTHORITY_FLOOR:g})"

    contradiction = len(set(stated.values())) > 1
    qualifying = {sid: fig for sid, fig in stated.items() if sid not in disregarded}
    candidates = set(qualifying.values())
    if len(candidates) != 1:
        return Assessment(0.0, contradiction, None, [], disregarded, unresolved=len(candidates) > 1)

    (winner,) = candidates
    best_per_origin: dict[str, str] = {}
    for sid in sorted(qualifying, key=lambda s: -by_id[s]["authority_weight"]):
        root = origin(sid, by_id)
        if root in best_per_origin:
            disregarded[sid] = f"copy: rests on {root}, already counted via {best_per_origin[root]}"
        else:
            best_per_origin[root] = sid
    supporting = sorted(best_per_origin.values())
    score = round(sum(by_id[sid]["authority_weight"] for sid in supporting), 2)
    return Assessment(score, contradiction, format_figure(winner), supporting, disregarded)
