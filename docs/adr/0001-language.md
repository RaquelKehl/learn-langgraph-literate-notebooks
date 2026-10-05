# ADR 0001: UK English throughout

**Status:** Accepted (4 October 2026). Supersedes the earlier decision for
German prose with English code (20 August 2026).

## Context

The notebooks are published in a public repository and are read by anyone
who finds it. LangGraph's own documentation, its community
and most of the material a reader would consult next are in English.

## Decision

Everything is written in UK English: notebook prose, code, identifiers,
docstrings, documentation, the corpus and commit messages. Prose avoids
dashes as sentence punctuation.

Two reasons decided it:

1. The best learning material for LangGraph is in English, for example
   LangChain Academy's course
   [Introduction to LangGraph](https://academy.langchain.com/courses/intro-to-langgraph)
   and the official documentation. Notebooks in the same language let readers
   move between them without translating terms.
2. Every student in the degree programme has declared at least an
   intermediate or business level of English, which is an entry requirement.
   Every reader in the module can therefore follow the notebooks.

## Alternatives considered

- **German prose, English code** (the previous decision): close to the
  module's teaching language, but splits every notebook into two languages
  and limits the public repository to German readers.
- **Bilingual versions:** double maintenance, not proportionate for a
  semester project.

## Consequences

- One language from prose to code; snippets and terms match the LangGraph
  documentation directly.
- Notebooks 01 and 02 and all German planning documents had to be rewritten.
