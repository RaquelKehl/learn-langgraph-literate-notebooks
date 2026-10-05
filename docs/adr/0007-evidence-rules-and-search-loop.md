# ADR 0007: Evidence rules and the search loop

**Status:** Accepted (4 October 2026). P6 measured and fixed on 5 October 2026
(see "Measurement of P6" below).

## Context

The assistant decides from fixed rules whether the evidence is good enough to
answer, whether to search again, or whether to stop and state a limitation.
These rules determine whether each corpus test works, and from NB 03 on,
notebook text, tests and scripted model responses are built on them. A review
of the first draft found two weaknesses:

- with a static corpus and a deterministic search, rounds 2 and 3 of the loop
  returned the same documents as round 1, so the loop was decoration rather
  than demonstrated control flow;
- one of the two promised reasons for human review in NB 06 (two credible
  sources contradicting each other) had no case in the corpus.

## Decision

**Parameters.**

| # | Parameter | Value |
|---|---|---|
| P1 | Authority floor for a source to count as evidence | 0.5 |
| P2 | Quality gate | at least two independent qualifying sources AND summed authority of at least 1.0 |
| P3 | Contradictions | always flagged; resolved automatically only when the opposing side is below the floor or outdated; otherwise no confident answer |
| P4 | Outdated source | a newer source covers the same point AND the gap is at least 12 months |
| P5 | Maximum search rounds | 3 |
| P6 | Relevance rule, rare words weighted above common ones | a document must name the question's subject (if the question names one) and reach 60% of the best match; measured |

**The threshold is fixed; only the retrieval strategy changes.** Round 1
searches with the terms of the question, round 2 with the question rephrased
by the model using domain synonyms, round 3 with broader terms for the
overall subject. The relevance cut-off stays the same in every round.

**A corpus document E4 is added** (21 documents in total): an independent,
credible source in topic e that confirms the correct figure but uses
different vocabulary, so only the rephrased query of round 2 finds it.

**Expected round counts are fixed per topic and asserted in tests:** topics a,
b and d need one round; topic e is rescued in round 2; topic c exhausts all
three rounds and stops with a stated limitation.

**`interrupt()` fires on exactly two triggers:** the gate still fails after
the last round (topic c), and two qualifying sources contradict each other on
a fact. The second trigger has no corpus case, so NB 06 constructs one openly
(a variant of topic a with an added news report at authority 0.7 stating
CHF 320 million) and says that the case is constructed.

**Supporting decisions.** P6 is chosen from measured corpus scores, not
estimated. The sensitivity of the parameters becomes NB 05's exercise (set the
floor to 0.3 and explain what happens to topic e). NB 02 and NB 06 make no
new model call, and their prompt logs say so instead of inventing iterations.

## Measurement of P6 (5 October 2026)

Relevance is the sum of the inverse document frequencies of the question's
words that a document contains. Eight queries were measured: the canonical
question of topics a to e and the planned round 2 and round 3 queries. For
each query, the cut-off must lie above the best-scoring document that must
not be retrieved and at or below the weakest document that must be.

**The provisional 50% failed twice.** For the revenue question in topic a,
the garden newsletter F1 (0.54 of the best match) scored above the forum
post A3 (0.46): no single cut-off could keep A3 and exclude F1. For the fee
question in topic e, the merger press release B1 (0.56) would have been
retrieved.

**No weighting of word frequencies solved it.** Plain, squared and cubed
inverse document frequency, and counting rare words only, all left the same
conflict. In a corpus of 21 documents, "third quarter" is as rare as
"Solvane": both occur in three documents. Statistics cannot tell the
question's subject from its time period.

**Final rule.** (1) If the question names a subject, meaning capitalised
words after the first (Solvane, AMSA, Brunnhof; period abbreviations such as
"Q3" excluded), a document must contain one of those names. (2) Period
abbreviations are expanded before matching ("Q3" becomes "third quarter"),
because financial texts write periods in shorthand. (3) A document must
reach the cut-off share of the best match.

**Measured valid range for the cut-off: above 0.56, at most 0.66. Fixed
value: 0.6.** The binding cases are B1 for the topic e question (0.56, must
be excluded) and the law-firm blog C2 for the topic c question (0.66, must be
retrieved). The margins are narrow: 0.04 and 0.06. `tests/test_retrieval.py`
pins the exact set of documents for every query, so any corpus edit that
moves a document across the line fails the tests.

Canonical questions, fixed with this measurement:

| Topic | Question |
|---|---|
| a | What revenue did Solvane Dynamics report for the third quarter of 2025? |
| b | What is the implied transaction value of the merger between Talvero Bank and Nordquist Privatbank? |
| c | What share of client crypto assets must be kept in cold storage under the new AMSA custody rules? |
| d | What is Brunnhof Versicherungen's current dividend payout target? |
| e | What is the average annual fee of robo-advisory platforms in Switzerland in 2025? |

The topic e question says "in Switzerland" rather than "Swiss" because the
newsletter E2 never uses the word "Swiss"; with "Swiss" as the subject name,
E2 would not be retrieved.

## Confirmation in NB 04 (5 October 2026)

The round 2 and round 3 queries were written live by `qwen3:8b` and recorded.
Topic e, round 2: *"What is the typical yearly charge of automated investment
services in Switzerland for 2025?"* finds E4, and the evidence score rises from
0.85 to 1.65. Topic c, rounds 2 and 3, finds no further figure, and the search
stops after round 3 with a stated limitation. A naive "rephrase the question"
prompt kept the question's own words and did not find E4. The expected round
counts (a, b, d: 1; e: 2; c: 3) hold and are asserted in `tests/test_loop.py`.

## Confirmation in NB 06 (5 October 2026)

Both review triggers fire as specified. Topic c pauses at `human_review` after
round 3. The constructed report X1 (fictional, authority 0.7, CHF 320 million,
its claim recorded from `qwen3:8b`) pauses topic a in round 1, and the reviewer
sees the competing figures with their sources. Approval and rejection end on
different nodes, and a paused run resumes from a SQLite file after a restart.
All four other topics are answered without a pause.

## Alternatives considered

- **Relax the relevance cut-off in later rounds:** rejected. At 35% the
  cycling club notice (authority 0.5) shares "new", "requirements" and
  "regulation" with the question in topic c, would count as a second source
  and would let the assistant answer a custody question from a club's helmet
  rules.
- **Admit documents below the authority floor in later rounds:** rejected.
  Below-floor documents are already read for contradiction checks (P3);
  admitting them as evidence would undo P1.
- **Semantic search with embeddings** (for example `bge-m3`, which runs
  locally): would separate subject from time period without a naming rule,
  but needs precomputed vectors to stay deterministic in CI and makes
  retrieval much harder to explain in a notebook. Mentioned in NB 03 as the
  production alternative.
- **Only an authority sum (P2 without the independence condition):**
  equivalent on this corpus, but it hides the audit principle that no answer
  rests on one source alone.
- **Rely on corpus cases only for NB 06:** rejected, because one of the two
  human-review branches would then never run.

## Consequences

- The loop demonstrably succeeds once (topic e) and demonstrably reaches its
  limit once (topic c), which answers research question 1 with observed
  behaviour.
- Round 2 needs a model call, which gives NB 04 a genuine prompt iteration
  (a naive paraphrase finds nothing new; asking for domain synonyms finds E4).
  The model influences what is searched for, never which edge runs next
  ([ADR 0004](0004-deterministic-routing.md)).
- Topic e also ends round 1 below the gate (only one qualifying source), which
  is the honest result before E4 is found.
- Changing any value after NB 05 means rewriting notebook text, fixtures and
  tests; the values are therefore frozen from 4 October 2026.
