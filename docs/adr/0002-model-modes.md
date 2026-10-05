# ADR 0002: Three model modes, with the fake model mandatory in CI

**Status:** Accepted (20 August 2026, revised 4 October 2026)

## Context

The notebooks must run deterministically in CI (GitHub Actions: no GPU, no
API key, no network access to model APIs). At the same time, a real language
model is needed locally for live demonstrations, genuine prompt iteration and,
from NB 05 on, for showing that real models misjudge evidence.

## Decision

A model factory (`src/research_assistant/models.py`) wraps three modes behind
the environment variable `LLM_MODE`:

- **`fake`** (default, mandatory in CI): `ScriptedChatModel`, a deterministic
  model driven by versioned YAML fixtures in `fixtures/fake_llm/`. It fails
  loudly when no fixture matches instead of improvising. Every fixture
  response from NB 01 on is recorded from `qwen3:8b`, including the
  misjudgements in NB 05, so replayed behaviour is real model behaviour.
- **`ollama`** (optional, local only): `qwen3:8b` via `langchain-ollama`,
  temperature 0, with the model's "thinking" switched off by default
  (`OLLAMA_REASONING=false`): measured on 4 October 2026, thinking took
  about 60 seconds per answer instead of about 5, with the same result.
  Never part of CI, never acceptance evidence.
- **`disabled`:** no model, for cells that demonstrate pure graph logic.

## Alternatives considered

- **Ollama as the CI baseline:** rejected. Even at temperature 0, outputs
  vary between runs; a test suite that turns red without a cause destroys
  trust in genuine regressions.
- **A hosted API as the CI baseline:** rejected. Cost, network dependency and
  key management in a public repository are needless risk for a teaching
  project.

## Consequences

- CI is fast, free and fully reproducible.
- Every new LLM call needs a versioned fixture.
- Live results are illustrations, not evidence. The gap between scripted and
  live behaviour is discussed openly in NB 05 and NB 07.
