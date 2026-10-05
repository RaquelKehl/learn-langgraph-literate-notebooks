# ADR 0005: One graph, no multi-agent design

**Status:** Accepted (4 October 2026). Replaces the earlier ADR on shared and
private state between agents, which no longer applies.

## Context

The earlier plan included a multi-agent notebook (researcher, analyst and
writer with shared and private state). The lecturer's concept sets a total
budget of 50 to 60 hours and explicitly recommends against a multi-agent
design.

## Decision

The series builds one graph with coordinated nodes. State consistency
(research question 2) is shown across those nodes through the state
contract, reducers and, in NB 06, persistence.

## Alternatives considered

- **Supervisor pattern with several agents:** estimated at 20 to 30 extra
  hours for coordination logic, debugging emergent behaviour and a state
  contract for several actors. Not justified within the budget.
- **Multi-agent as an optional closing notebook:** rejected, because it would
  compete for time with persistence and the LLM-misjudgement notebook, which
  both serve the research questions directly.

## Consequences

- Seven notebooks instead of eight, each focused on one concept.
- NB 07 closes with a multi-agent outlook: the three working nodes
  (retrieval, scoring, synthesis) become three agents behind a supervisor
  that controls routing, with the state contract as the shared coordination
  mechanism, mapped to LangGraph's subgraph pattern. This answers the
  original assignment wording ("several cooperating agents") without
  building it, and stays consistent with the lecturer's reframing as
  coordinated nodes.
