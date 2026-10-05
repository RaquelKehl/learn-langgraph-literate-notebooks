# Frequently asked questions

Short answers for readers and reviewers. If a question is missing here,
[open an issue](https://github.com/RaquelKehl/learn-langgraph-literate-notebooks/issues/new?template=notebook-feedback.md).

**Contents:** [The project](#the-project) · [Setup](#setup) ·
[Model modes](#model-modes) · [Deliberate mistakes](#deliberate-mistakes) ·
[The diagram](#the-diagram) · [Feedback](#feedback) · [Licence](#licence)

## The project

### What is this repository?

Seven Jupyter notebooks that teach LangGraph through literate programming.
Together they build one evidence-based research assistant over a small,
fictional finance corpus: it searches documents, lets a language model read
one figure per document, judges the evidence with fixed rules, searches again
when the evidence is thin, and pauses for a person when it stays uncertain.

### Where do I start?

With [NB 01](notebooks/01_hello_langgraph.ipynb), then in order. Each notebook
builds on the previous one, and every notebook has the same eight parts:
learning goals, setup, concept, experiment, common mistakes, prompt log,
summary and exercise. [NB 07](notebooks/07_synthesis.ipynb) answers the four
research questions with evidence from the other six.

### Can I just read the notebooks on GitHub?

Yes. GitHub shows the text and the code. The notebooks are stored **without
outputs**, so results such as scores, routes and error messages only appear
when a notebook runs. The concept, mistakes and prompt log sections read well
without running anything; the experiments make more sense with a run (see
[Setup](#setup)).

### Why are the outputs not stored?

Stored outputs go stale as soon as the code changes, and they make every
change hard to review. Instead, the test suite runs every notebook from top to
bottom on each push, so the code shown is the code that works.

### Why English?

The best LangGraph material, including the official documentation and
LangChain Academy's course *Introduction to LangGraph*, is in English, so terms
and code match without translation. See [ADR 0001](docs/adr/0001-language.md).

### Why a fictional corpus?

Every case is built in on purpose: a contradiction, an outdated figure, a copy
that looks like a second source, a document that only a rephrased search finds,
and newsletters that have nothing to do with finance. Because the cases are
known, every outcome can be tested. The cost: nothing here measures
performance on real documents. See [ADR 0003](docs/adr/0003-fictional-corpus.md).

### Why does the model only read and never decide?

The model extracts figures and rewrites search queries. Fixed rules decide
which sources count, and a router decides what happens next. NB 05 shows why:
asked to judge the evidence itself, the model missed a contradiction, was
confident on a single source and counted a copy as independent confirmation.
See [ADR 0004](docs/adr/0004-deterministic-routing.md).

### Why is there no multi-agent version?

It was left out of scope on purpose: one graph with clearly separated nodes
answers the research questions, and a multi-agent design would have needed
far more time for coordination and debugging. NB 07, section 6, sketches how
the existing nodes would become agents behind a supervisor. See
[ADR 0005](docs/adr/0005-single-graph-no-multi-agent.md).

## Setup

### What do I need?

Python 3.12 and Git. No API key, no GPU, and after installation no internet
connection. A real language model is optional (see [Model modes](#model-modes)).

### How do I install and start it?

```bash
git clone https://github.com/RaquelKehl/learn-langgraph-literate-notebooks.git
cd learn-langgraph-literate-notebooks
python -m venv .venv
```

Activate the environment, then install and start JupyterLab:

| System | Activate |
|---|---|
| Windows, Command Prompt | `.venv\Scripts\activate` |
| Windows, Git Bash | `source .venv/Scripts/activate` |
| macOS, Linux | `source .venv/bin/activate` |

```bash
pip install -r requirements.txt
pip install -e .
jupyter lab
```

### Does it have to be Python 3.12?

That is the version the project is tested with, locally and in CI. Check with
`python --version`. If several versions are installed on Windows,
`py -3.12 -m venv .venv` creates the environment with 3.12.

### PowerShell refuses to activate the environment.

PowerShell blocks scripts by default on many machines. The simplest way round
it is to use Command Prompt or Git Bash for the commands above instead of
changing any system setting.

### `ModuleNotFoundError: No module named 'research_assistant'`

The notebooks import the tested code from the package in `src/`. Run
`pip install -e .` inside the activated environment, and start `jupyter lab`
from that same environment so the notebooks use its Python.

### How do I check that everything works?

```bash
pytest
```

This runs all unit tests and executes every notebook in the default mode. It
takes one to two minutes and should end with `passed` and no failures.

## Model modes

### Do I need a language model?

No. By default (`LLM_MODE=fake`) the notebooks use a scripted stand-in that
replays replies **recorded from a real local model**, `qwen3:8b`. Every run
gives the same result, which is what the tests rely on.

### How do I try a real model?

1. Install [Ollama](https://ollama.com).
2. Run `ollama pull qwen3:8b` (a download of several gigabytes).
3. Copy `.env.example` to `.env` and set `LLM_MODE=ollama`.
4. Restart the notebook kernel.

Live runs are much slower than scripted ones, and cells marked `live-only`
now run as well.

### The live model says something slightly different from the notebook text.

Expected. Even at temperature 0, a model does not always word its reply the
same way; NB 04 documents an example in its prompt log. That is why the tests
compare complete runs only in the scripted mode.

### `no fixture rule matches prompt`

The scripted model only knows the prompts that were recorded. A new question
or a changed prompt has no recorded reply, and the scripted model refuses
rather than invent one. Either switch to `LLM_MODE=ollama` or add a rule to
the matching file in `fixtures/fake_llm/`. The NB 01 exercise walks through
exactly this.

### Why does NB 07 ignore `LLM_MODE`?

NB 07 synthesises evidence. It always uses the recorded replies, so it cites
the same evidence on every run.

## Deliberate mistakes

### Some cells end with an error. Is something broken?

No. Every notebook has a "Common mistakes" section with cells that fail on
purpose, each followed by an explanation and the fix. These cells carry the
tag `raises-exception` and declare the exact error they must raise; the test
suite fails if they raise anything else, or nothing at all.

### "Run all" stopped at the first mistake.

Jupyter uses the `raises-exception` tag to continue past these cells. If your
version stops anyway, select the next cell and choose *Run Selected Cell and
All Below*.

### Some mistakes show no error at all.

Those are the silent ones, such as a node that forgets to return its update:
the run completes and the data is simply wrong. These cells check the effect
with an `assert`, which is part of the lesson.

## The diagram

### The architecture diagram in the README does not move.

It is an animated SVG that loops for about 40 seconds. If it stays still,
check that animations are switched on in the operating system (Windows:
Settings, Accessibility, Visual effects, *Animation effects*; macOS: System
Settings, Accessibility, Display, *Reduce motion* off). With reduced motion,
the diagram deliberately shows a still picture. It can also be opened on its
own: [docs/architecture.svg](docs/architecture.svg). GitHub's *Raw* button
shows the SVG source code, not the picture.

### Is the diagram accurate?

It is checked against the code: six tests in `tests/test_architecture.py` fail
if a node, a state field, a router decision or a printed threshold in the
picture no longer matches the implementation.

## Feedback

### What feedback helps most?

1. **Concept sections:** after reading one, could you explain the idea to
   someone else?
2. **Common mistakes:** did each one teach you something, and is the fix
   convincing?
3. **Exercises:** could you solve them without a hint?
4. **Setup:** did the quick start work on your machine? If not, where did it
   stop?

Short notes are fine. A single unclear sentence, with the notebook and
section, is already useful.

### How do I send it?

[Open an issue](https://github.com/RaquelKehl/learn-langgraph-literate-notebooks/issues/new?template=notebook-feedback.md)
with the feedback template, one issue per notebook. Issues in a public
repository are public and show your GitHub name. If you were invited to
review the series and prefer not to comment in public, reply through the
channel the invitation came from.

### Do I need to run the code to give feedback?

No. Points 1 to 3 can be answered by reading on GitHub. Only point 4 needs an
installation.

## Licence

Code, including the code cells in the notebooks, is under the
[MIT licence](LICENSE). Prose, documentation, the diagram and the corpus are
under [CC BY 4.0](LICENSE-CONTENT.md). Details in [NOTICE.md](NOTICE.md).
