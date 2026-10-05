# ADR 0003: A fictional, local finance corpus in Markdown

**Status:** Accepted (20 August 2026, revised 4 October 2026: the domain
changed from AI governance to finance)

## Context

The research assistant needs documents in which evidence, contradictions and
source quality can be demonstrated. The project belongs to the module Digital
Finance, and the repository is public.

## Decision

About 20 self-written documents in six topic folders under `data/corpus/`,
Markdown with YAML front matter (`source_id`, `topic`, `type`, `publisher`,
`date`, `authority_weight`). Five topics are fictional finance cases
(quarterly earnings, a merger, a regulatory change, outdated data, a market
analysis), each with a built-in test case; the sixth is an unrelated control
topic. Every company, person and event is fictional and marked as such. No
PDFs or Word files, no web search.

## Alternatives considered

- **Real financial or regulatory texts:** copyright and topicality risks in a
  public repository, and real facts cannot be bent to produce exactly the
  contradiction each notebook needs.
- **The earlier AI-governance corpus of a fictional company:** replaced,
  because a finance domain fits the module and the lecturer's concept.
- **Word documents:** an extra dependency, not diffable, less robust in CI.

## Consequences

- The author controls documents, metadata and expected answers completely,
  which makes deterministic fixtures possible.
- A loader test validates the front matter of every document, so a broken
  file fails CI rather than a notebook.
