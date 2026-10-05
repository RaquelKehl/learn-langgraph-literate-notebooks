"""Notebook runner: executes every notebook with a fresh kernel and
enforces the cell contracts from the project conception.

Contract per code cell:
- normal cell:          any exception fails the run;
- tag "raises-exception": the cell MUST fail, and only with the exception
  type named in the cell metadata field "expected_exception" (fully
  qualified or bare class name; optional "expected_match" regex on the
  message). A missing declaration, a missing error, or a different error
  type all fail the run;
- tag "live-only":      removed before execution unless LLM_MODE=ollama.

Notebooks are parametrised in filename order (01..07), so one pytest run
covers both "each notebook alone, fresh kernel" and "the whole sequence".
"""
import os
import re
from pathlib import Path

import nbformat
import pytest
from nbclient import NotebookClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = sorted((PROJECT_ROOT / "notebooks").glob("*.ipynb"))

EXECUTION_TIMEOUT = 300


def _tags(cell) -> set:
    return set(cell.get("metadata", {}).get("tags", []))


def _strip_live_only(nb) -> int:
    """Remove live-only cells when no live model is available."""
    before = len(nb.cells)
    nb.cells = [c for c in nb.cells if "live-only" not in _tags(c)]
    return before - len(nb.cells)


def _check_cell_contracts(nb, nb_name: str) -> list:
    problems = []
    for index, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        errors = [o for o in cell.get("outputs", []) if o.output_type == "error"]
        where = f"{nb_name}, cell {index}"
        if "raises-exception" in _tags(cell):
            expected = cell.metadata.get("expected_exception")
            if not expected:
                problems.append(
                    f"{where}: tag raises-exception without metadata "
                    "expected_exception: incomplete error contract"
                )
            elif not errors:
                problems.append(
                    f"{where}: expected error {expected} did not occur"
                )
            else:
                ename = errors[0]["ename"]
                evalue = errors[0].get("evalue", "")
                if ename != expected.rsplit(".", 1)[-1]:
                    problems.append(
                        f"{where}: expected {expected}, got {ename}: {evalue}"
                    )
                expected_match = cell.metadata.get("expected_match")
                if expected_match and not re.search(expected_match, evalue):
                    problems.append(
                        f"{where}: error message {evalue!r} does not match "
                        f"expected_match {expected_match!r}"
                    )
        elif errors:
            problems.append(
                f"{where}: unexpected error "
                f"{errors[0]['ename']}: {errors[0].get('evalue', '')}"
            )
    return problems


@pytest.mark.parametrize("nb_path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook(nb_path):
    # Set explicitly so a local .env (read by load_dotenv() in each notebook)
    # cannot switch a test run to a live model.
    llm_mode = os.environ.setdefault("LLM_MODE", "fake")
    nb = nbformat.read(nb_path, as_version=4)

    if llm_mode != "ollama":
        _strip_live_only(nb)

    client = NotebookClient(
        nb,
        timeout=EXECUTION_TIMEOUT,
        kernel_name="python3",
        allow_errors=True,  # error contracts are checked below
        resources={"metadata": {"path": str(nb_path.parent)}},
    )
    client.execute()

    problems = _check_cell_contracts(nb, nb_path.name)
    assert not problems, "\n".join(problems)


def test_notebooks_exist():
    assert NOTEBOOKS, "no notebooks found under notebooks/"


# --- Unit tests for the contract checker itself: the runner must actually
# --- reject wrong, missing and unexpected errors.


def _fake_cell(tags=None, expected=None, error=None, match=None):
    cell = nbformat.v4.new_code_cell("pass")
    if tags:
        cell.metadata["tags"] = tags
    if expected:
        cell.metadata["expected_exception"] = expected
    if match:
        cell.metadata["expected_match"] = match
    if error:
        cell["outputs"] = [
            nbformat.v4.new_output(
                "error", ename=error[0], evalue=error[1], traceback=[]
            )
        ]
    return cell


def _nb_with(cell):
    nb = nbformat.v4.new_notebook()
    nb.cells = [cell]
    return nb


def test_contract_accepts_expected_error():
    cell = _fake_cell(
        tags=["raises-exception"], expected="ValueError", error=("ValueError", "x")
    )
    assert _check_cell_contracts(_nb_with(cell), "t") == []


def test_contract_rejects_wrong_error_type():
    cell = _fake_cell(
        tags=["raises-exception"], expected="ValueError", error=("KeyError", "x")
    )
    assert _check_cell_contracts(_nb_with(cell), "t")


def test_contract_rejects_missing_error():
    cell = _fake_cell(tags=["raises-exception"], expected="ValueError")
    assert _check_cell_contracts(_nb_with(cell), "t")


def test_contract_rejects_undeclared_expectation():
    cell = _fake_cell(tags=["raises-exception"], error=("ValueError", "x"))
    assert _check_cell_contracts(_nb_with(cell), "t")


def test_contract_rejects_error_in_normal_cell():
    cell = _fake_cell(error=("RuntimeError", "boom"))
    assert _check_cell_contracts(_nb_with(cell), "t")


def test_contract_checks_message_regex():
    cell = _fake_cell(
        tags=["raises-exception"],
        expected="ValueError",
        error=("ValueError", "unrelated message"),
        match="entrypoint",
    )
    assert _check_cell_contracts(_nb_with(cell), "t")


def test_live_only_cells_are_stripped():
    nb = _nb_with(_fake_cell(tags=["live-only"]))
    assert _strip_live_only(nb) == 1
    assert nb.cells == []
