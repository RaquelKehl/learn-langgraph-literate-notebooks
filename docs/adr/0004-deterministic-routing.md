# ADR 0004: Routing and scoring are deterministic Python

**Status:** Accepted (20 August 2026, revised 4 October 2026)

## Context

LangGraph lets an LLM decide which edge runs next. For a teaching project
with mandatory CI, the control flow itself has to stay readable and testable.
Research question 4 also asks where rule-based heuristics reach their limits,
which needs a rule-based baseline to compare against.

## Decision

Readable Python decides the control flow: the scoring node computes
`evidence_score` and `contradiction_flag` from source count, authority weight
and contradiction rules, and the router compares them with a threshold. The
LLM writes answers and, in NB 05, makes the evidence judgements under test.
It never chooses the next edge.

## Alternatives considered

- **An LLM router or supervisor:** rejected. Tests would become
  nondeterministic and the control flow the notebooks set out to explain
  would disappear inside the model.
- **LLM-only evidence assessment:** rejected as the baseline, because NB 05
  needs a deterministic reference against which the LLM's misjudgements
  become visible.

## Consequences

- Routing and scoring are covered by ordinary unit tests.
- Rule-based scoring has blind spots of its own (it cannot tell that two
  agreeing sources copy each other unless a rule says so). NB 05 and NB 07
  discuss these limits explicitly.
