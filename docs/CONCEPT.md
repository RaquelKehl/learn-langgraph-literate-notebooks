# Concept: Learning LangGraph through Literate Programming

Version 3 (4 October 2026). Supersedes the German concept v2.1. Based on the
lecturer's extended project concept (DIFA, August 2026), which in turn builds
on the author's own draft.

## 1 Purpose

An evidence-based research assistant over a small, controlled, self-written
document corpus, built with LangGraph. The assistant itself is not the point.
The point is to show how the core LangGraph concepts (state management,
routing, loops, persistence) emerge step by step in one continuous system,
following the principle of literate programming: code and explanation form a
single document, with Jupyter notebooks as the modern medium.

The notebooks are self-contained: concepts, code, mistakes and the answers to
the research questions all live in them.

## 2 Architectural core

One pattern runs through the whole series:

```
Retrieve -> Score -> Loop until quality gate -> Finalise
```

1. Documents relevant to a question are retrieved.
2. They are scored against rule-based criteria: number of sources, authority
   weight, contradiction detection.
3. If the evidence is insufficient, the assistant searches again
   (re-retrieval loop).
4. Only when the evidence passes the quality gate is an answer synthesised.

An explicit **state contract** defines who owns each state field and under
which rules it may change. Deliberate mistakes, both technical (state,
reducers, control flow) and in content (the LLM misses a contradiction or
overrates a weak source), make typical pitfalls visible and are part of the
teaching.

### Scope decision: one graph, no multi-agent design

The series deliberately avoids a multi-agent design (several cooperating
agents with a supervisor). Within a budget of 50 to 60 hours, the extra cost
of coordination logic, debugging emergent behaviour and a state contract for
several actors would not be justified. State consistency is demonstrated
across coordinated nodes within a single graph instead, which covers research
question 2 fully. See [ADR 0005](adr/0005-single-graph-no-multi-agent.md).

## 3 Research questions

1. How does LangGraph's graph-based control flow differ from linear chain
   approaches, and at which concrete point in the research process (for
   example insufficient evidence that requires re-retrieval) does a linear
   chain become structurally inadequate?
2. How can a shared state be kept consistent across several coordinated
   processing steps (nodes), and what does an explicit state contract with
   defined field ownership contribute to avoiding inconsistent states?
3. How can concepts, code and typical mistakes, including deliberately
   provoked misjudgements by the LLM itself and not only implementation
   errors, be woven together so that a common thread runs through the
   notebook series?
4. How can the quality of evidence be assessed in an LLM-supported research
   process, and where are the limits of rule-based heuristics compared with
   cases in which the LLM itself overlooks contradictions or weights sources
   wrongly?

## 4 Fixed structure of every notebook

| Section | Content |
|---|---|
| Learning goals | Markdown: 3 to 5 bullet points on what the reader can do afterwards |
| Setup cell | Code: imports, `load_dotenv()`, version check; must run on a fresh virtual environment |
| Concept | Markdown: the core idea, ideally with a small graph sketch, before any code appears |
| Experiment | Code and Markdown alternating; every code cell is preceded by an explanation |
| Common mistakes | At least two typical mistakes with deliberately wrong code, the error, and a corrected version with reasoning |
| Prompt log | Markdown: iterated prompts with version history (first version, problem, final version, insight) |
| Summary | Markdown: what was built, and a preview of the next notebook |
| Exercise | Markdown plus an empty code cell: a concrete task for the reader |

Where a section does not apply (for example a prompt log in a notebook
without an LLM call), the section stays and says so in one sentence, so the
structure remains identical across the series.

Every prompt log shows a genuine iteration, in which a first prompt exposed a
real weakness. Iterations are never invented to fill the section:

| NB | Prompt under iteration |
|---|---|
| 01 | writing the answer from a document |
| 02 | none: no new model call; the section says why |
| 03 | extracting the stated figure from a document as structured data (a first prompt returns prose) |
| 04 | rephrasing the question for round 2 (a naive paraphrase finds nothing new; asking for domain synonyms finds the missing source) |
| 05 | judging the evidence, run live against `qwen3:8b`, with a marked scripted fallback |
| 06 | none: no new model call; the section says why |
| 07 | none: synthesis notebook |

## 5 The seven notebooks

| # | Notebook | Core content | RQ |
|---|---|---|---|
| 01 | `01_hello_langgraph.ipynb` | One question, one hard-coded document, one answer: built once as an LCEL chain (`prompt \| llm \| parser`) and once as a `StateGraph` (`add_node`, `add_edge`, `compile()`, `invoke()`). Same result, different structure. No retrieval, no corpus, no scoring. | 1 |
| 02 | `02_state_contract.ipynb` | State schema (`documents`, `evidence_score`, `contradiction_flag`, `draft_answer`, `history`), reducer functions, explicit ownership and change rules. | 2 |
| 03 | `03_retrieval_and_scoring.ipynb` | Load the corpus, retrieval node, rule-based evidence scoring (independent sources, authority weight, contradiction detection, outdated sources). The relevance cut-off is measured on the corpus, not guessed. A short section on who assigns authority weights in practice and why hand-assigned weights are a limitation. The unrelated control topic checks that retrieval filters cleanly. | 4 |
| 04 | `04_conditional_routing_and_loops.ipynb` | Router node "enough evidence?": continue to synthesis or loop back to re-retrieval with a different query strategy per round. Topic e is rescued in round 2, topic c exhausts all three rounds and stops. `add_conditional_edges`, `recursion_limit`, a business stop condition. | 1, 3 |
| 05 | `05_llm_misjudgement.ipynb` | The model judges the evidence itself, in a fixed JSON verdict compared field by field with the rules. Recorded from `qwen3:8b`: a missed contradiction, confidence on one source, copies taken as independent, a resolved contradiction blurred into none; recency judged correctly. Metadata, a reworded prompt and thinking mode tested. | 3, 4 |
| 06 | `06_persistence.ipynb` | Checkpointer (`InMemorySaver`, then `SqliteSaver` in a local file: no account, no API key), `interrupt()` on the two triggers in section 8 (topic c after round 3; an openly constructed credible contradiction in round 1), approval and rejection on different routes, a resume after a restart, and the checkpoint history as an audit trail. | 2 |
| 07 | `07_synthesis.ipynb` | Answers to the four research questions, each linked to the notebook that demonstrates it; chain versus graph comparison; limits of the approach; a multi-agent outlook (the three working nodes as three agents behind a supervisor, mapped to LangGraph's subgraph pattern). Mostly Markdown. | all |

Technical mistakes live where they arise (a forgotten reducer in NB 02, a
missing stop condition in NB 04), as the notebook template requires. NB 05 is
reserved for misjudgements in content, which is the new material for research
question 4.

## 6 Error catalogue

Every deliberate error cell carries the tag `raises-exception` plus the cell
metadata `expected_exception`. The notebook runner accepts only the declared
exception type. Silent errors (no exception, wrong effect) are checked with an
`assert` on the effect instead. Exception types marked "to verify" are
confirmed against the pinned LangGraph version when the notebook is built.

| ID | NB | Mistake | Check |
|---|---|---|---|
| NB01-E01 | 01 | `compile()` without an entry edge from `START` | `ValueError` |
| NB01-E02 | 01 | A node returns a plain string instead of a partial state update | `InvalidUpdateError` |
| NB01-E03 | 01 | The chain prompt references a variable that is never supplied | `KeyError` |
| NB02-E01 | 02 | A node forgets its `return`: the update is lost without any error | effect assert |
| NB02-E02 | 02 | Two parallel nodes write `documents` without a reducer | `InvalidUpdateError` |
| NB02-E03 | 02 | A node writes a field it does not own (LangGraph allows it; the contract check does not) | `ContractViolation` |
| NB03-E01 | 03 | Retrieval without any relevance rule lets the control topic leak into the results | effect assert |
| NB03-E02 | 03 | A corpus document without `authority_weight` | `KeyError` |
| NB03-E03 | 03 | Reading the model's free-text reply as data | `JSONDecodeError` |
| NB04-E01 | 04 | A loop without a business stop condition | `GraphRecursionError` |
| NB04-E02 | 04 | The router returns a label that is not in the path map | `KeyError` |
| NB04-E03 | 04 | `claims` without a merge rule: round 2 replaces round 1's claims, and the state contradicts the router's decision | effect assert |
| NB05-E01 | 05 | Trusting the model's "no contradiction" on topic a (it never mentions the CHF 310 million claim) | effect assert against the rule-based flag |
| NB05-E02 | 05 | Treating the model's "sufficient" as the quality gate (topic e: one source, called sufficient) | effect assert |
| NB05-E03 | 05 | Counting agreeing copies as independent confirmation (constructed: only E1 and E2 found; the model reports two independent sources despite "based on: E1") | effect assert |
| NB06-E01 | 06 | Pausing without a checkpointer: the pause looks normal, resuming fails | `RuntimeError` |
| NB06-E02 | 06 | Resuming on a misspelt `thread_id`: the graph starts from nothing and fails at its first node | `KeyError` |
| NB06-E03 | 06 | A reviewer decision outside `approve` and `reject` is refused at the boundary | `ValueError` |

The NB 05 misjudgements were recorded from `qwen3:8b` on 5 October 2026, not
invented; `LLM_MODE=fake` replays them, so they occur every time. The plan
expected a fourth one, an outdated source taken as current (topic d); the
model judged recency correctly, and NB 05 reports that. In `LLM_MODE=ollama`
a live model may answer differently; that variance is itself part of the
answer to research question 4.

## 7 State contract

Defined in `src/research_assistant/state.py`; the notebooks develop it and
the package consolidates it.

| Field | Owner | Reducer | Introduced |
|---|---|---|---|
| `question` | caller | overwrite | NB 01 |
| `documents` | collecting nodes: fixed documents in NB 02, primary and secondary source search from NB 03 | merge, deduplicated by `source_id`, sorted | NB 02 |
| `claims` | scoring node only | merge: keep claims already read, add new ones (from NB 04, when it is written in every round) | NB 03 |
| `evidence_score` | scoring node only | overwrite | NB 02 |
| `contradiction_flag` | scoring node only | overwrite | NB 02 |
| `draft_answer` | `write_answer`; in NB 04 also `write_limitation`; in NB 06 `publish_reviewed` and `withhold_answer` instead | overwrite | NB 01 |
| `history` | every node | append (`operator.add`) | NB 02 |
| `query` | `refine_query` only | overwrite | NB 04 |
| `retrieval_round` | `refine_query` only (absent in round 1) | overwrite | NB 04 |
| `review_decision` | `human_review`, with the value a person sends via `Command(resume=...)` | overwrite | NB 06 |

Fields with a single owner need no reducer; fields with several writers must
have one. LangGraph does not enforce ownership, so the contract is written
down as data (field to allowed nodes) and `check_contract()` verifies every
run against the updates reported by `stream()`.

Each entry in `documents` is a `SourceDoc`: `source_id`, `title`, `topic`,
`type`, `publisher`, `date`, `authority_weight`, `based_on` and `text`, built from
the corpus front matter by `to_source_doc()`.

## 8 Evidence rules and the search loop

The rules are fixed before the notebooks are built, so every corpus test has
a defined outcome. Decision record: [ADR 0007](adr/0007-evidence-rules-and-search-loop.md).

| # | Parameter | Value |
|---|---|---|
| P1 | Authority floor: a source counts as evidence only at or above | 0.5 |
| P2 | Quality gate: at least two independent qualifying sources AND their summed authority | at least 1.0 |
| P3 | Contradictions | always flagged; resolved automatically only when the opposing side is below the floor or outdated; otherwise no confident answer |
| P4 | Outdated: a newer source covers the same point AND the gap is | at least 12 months |
| P5 | Maximum search rounds (business stop condition) | 3 |
| P6 | Relevance rule, with rare words weighted above common ones | the document must name the question's subject (if the question names one) and reach 60% of the best match; measured, see ADR 0007 |

Independent means a different origin: documents linked by `based_on` count
once. The two conditions in P2 are equivalent on this corpus (no single weight
exceeds 0.95), but the first states the audit principle, no answer rests on
one source alone, and the second keeps the rule robust if weights change.

**The threshold is fixed; only the retrieval strategy changes.** Lowering the
cut-off in later rounds would let the control topic qualify as evidence (the
cycling club notice shares "new", "requirements" and "regulation" with the
question in topic c and has authority 0.5).

| Round | Query strategy |
|---|---|
| 1 | the terms of the question |
| 2 | the question rephrased by the model with domain synonyms |
| 3 | broader terms for the overall subject |

Expected outcome per topic, asserted in tests:

| Topic | Rounds | Outcome |
|---|---|---|
| a | 1 | CHF 342 million; the forum claim of CHF 310 million is flagged and noted as unsupported |
| b | 1 | the merger terms plus both assessments; no contradiction |
| c | 3 | gate still fails: answer from the circular with a stated limitation (NB 04), or a pause for human review (NB 06) |
| d | 1 | 45%, replacing the outdated 60% |
| e | 2 | round 2 finds a second independent source: 0.62%; the copied 0.38% is identified as weak and dependent |
| f | n/a | never retrieved |

`interrupt()` in NB 06 fires on exactly two triggers:

1. the quality gate still fails after the last round (topic c, from the
   corpus);
2. two qualifying sources contradict each other on a fact. No corpus topic
   produces this, so NB 06 constructs it openly: a variant of topic a with an
   added fictional news report (authority 0.7) stating CHF 320 million. The
   notebook says that the case is constructed.

## 9 Corpus design

Markdown files with YAML front matter, no `.docx`: no extra dependency,
diffable in a public repository, robust on a fresh virtual environment in CI.
All companies, people and events are fictional. Language: UK English.

```
data/corpus/
  topic_a_quarterly_earnings/
  topic_b_merger/
  topic_c_regulatory_change/
  topic_d_outdated_data/
  topic_e_market_analysis/
  topic_f_unrelated_control/
```

Six topics with three or four documents each, 21 documents in total (a 3,
b 3, c 4, d 4, e 4, f 3): small on purpose, so every case stays controllable
and traceable instead of producing retrieval noise. File names are neutral
(`a3_forum_post.md`, not `source_3_contradicting.md`), so no name gives a test
away.

Front matter of every document:

```yaml
source_id: A1                      # unique across the corpus
topic: topic_a_quarterly_earnings
type: press_release                # press_release, news_article, analyst_note, forum_post, ...
publisher: "Solvane Dynamics AG (Investor Relations)"
date: 2025-11-04
authority_weight: 0.9              # 0.0 to 1.0
based_on: [A1]                     # optional: sources this document copies or repeats
```

`based_on` makes provenance machine-readable, so a rule can count independent
origins instead of documents (topic e). Authority scale: 0.90 to 0.95 primary
official sources; 0.70 to 0.85 reputable secondary sources; 0.35 to 0.65
weaker secondary sources; 0.15 to 0.20 anonymous forum posts; 0.50 for the
control topic, so authority alone cannot filter it. Research questions are
asked as of 1 December 2025, which makes the age of a source testable
(topic d).

Distinctive names and terms are fenced per topic (a company name or a term
like "custody" appears in one topic only), because retrieval is plain keyword
matching and a stray name would pull documents into the wrong question.

| Topic | Content (fictional) | Built-in test case | NB |
|---|---|---|---|
| a quarterly earnings | Q3 2025 results of Solvane Dynamics AG | authority difference plus a factual contradiction (CHF 342m vs CHF 310m revenue) | 03, 05 |
| b merger | An all-share merger of two fictional private banks | three reputable sources agree on every fact but disagree in their assessment: a control case, no contradiction may be flagged | 05 |
| c regulatory change | A new custody circular of a fictional supervisory authority | only one usable source; three related documents carry no facts: triggers the re-retrieval loop and its stop condition | 04 |
| d outdated data | A fictional insurer's dividend payout target, 2023 versus 2025 | equally authoritative sources two years apart: only the date resolves 60% versus 45% | 05 |
| e market analysis | Average fees of fictional robo-advisory platforms | two weak sources agree on a wrong figure because one copies the other: the source-count fallacy; a fourth, independent source uses different vocabulary and is found only by the rephrased query in round 2 | 04, 05 |
| f unrelated control | Village club newsletters with no link to finance | shares everyday words with finance questions, must never be retrieved | 03 |

This resolves an inconsistency in the original topic list (topics d to f were
named differently in the folder list, the topic table and the NB 05
description).

## 10 Model modes and reproducibility

| `LLM_MODE` | Use | Purpose |
|---|---|---|
| `fake` | default; mandatory in tests and CI | scripted, versioned responses: no internet, GPU or API key |
| `ollama` | optional, local | `qwen3:8b` for live demos and real prompt iteration; enables `live-only` cells |
| `disabled` | optional | graph logic without any LLM |

- Python 3.12, installable package (`pip install -e .`, src layout).
- Universal lockfile (`uv pip compile --universal`); weekly compatibility run
  against unpinned dependencies.
- Every notebook runs on a fresh kernel, alone and as part of the sequence.
- Routing and scoring are deterministic Python. The LLM writes answers and,
  in NB 05, makes the judgements under test; it never decides control flow.
  See [ADR 0004](adr/0004-deterministic-routing.md).

## 11 Conventions

- **Language:** UK English throughout: notebook prose, code, documentation,
  commit messages. See [ADR 0001](adr/0001-language.md).
- **Style:** no dashes as sentence punctuation in notebook prose or
  documentation; commas, colons and full stops instead.
- **Code:** developed in the notebook, consolidated in `src/`. Each notebook
  imports the previous stage from the package and checks with an `assert`
  that its own version matches the consolidated one (drift guard).
- **Git:** the author is the only contributor; no tool attribution in commit
  messages.

## 12 Repository layout

```
src/research_assistant/   tested core logic (graph stages, state, scoring, LLM factory)
notebooks/                the seven notebooks (01 to 07), committed without outputs
data/corpus/              fictional finance corpus, six topic folders
fixtures/fake_llm/        versioned, deterministic fake-LLM responses
tests/                    unit tests plus notebook runner with error contracts
docs/                     this concept, the plan, architecture decision records
.github/workflows/        CI (lockfile, LLM_MODE=fake) and weekly compatibility check
```
