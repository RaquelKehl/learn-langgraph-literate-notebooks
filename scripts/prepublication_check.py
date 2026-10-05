"""Pre-publication check: run before the first push.

Checks the working tree and the history of the branch to be published.
Usage:  python scripts/prepublication_check.py [branch] [--allow-author-email ADDRESS]
Exit code 0 only if every check passes.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]
NOREPLY = "@users.noreply.github.com"
GITHUB_WEB = "noreply@github.com"  # the committer of edits made on github.com
SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9]{20,}",
    r"ghp_[A-Za-z0-9]{30,}",
    r"AKIA[0-9A-Z]{16}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
]
PERSONAL_PATTERNS = [
    r"[A-Za-z0-9._%+-]+@(?!users\.noreply\.github\.com)[A-Za-z0-9.-]+\.[A-Za-z]{2,}",  # e-mail addresses
    r"\+?\d{2,3} ?\d{2,3} ?\d{3} ?\d{2} ?\d{2}",  # phone numbers
]
ATTRIBUTION_PATTERNS = [r"(?i)co-authored-by:", r"(?i)generated with .*claude"]


def git(*args: str) -> str:
    # git writes UTF-8; the Windows default codec (cp1252) cannot decode every byte of a diff
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=True).stdout


def tracked_files() -> list[Path]:
    return [ROOT / name for name in git("ls-files").splitlines()]


def text_of(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, FileNotFoundError):
        return ""


def check_no_env_files() -> list[str]:
    return [str(p.relative_to(ROOT)) for p in tracked_files() if p.name == ".env" or p.suffix == ".sqlite"]


def check_no_secrets_in_tree() -> list[str]:
    hits = []
    for path in tracked_files():
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, text_of(path)):
                hits.append(f"{path.relative_to(ROOT)}: {pattern}")
    return hits


def added_lines(branch: str):
    """(commit, path, line) for every line any commit on the branch added."""
    commit = path = ""
    for line in git("log", branch, "-p", "--format=COMMIT %h").splitlines():
        if line.startswith("COMMIT "):
            commit = line.split()[1]
        elif line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else ""
        elif line.startswith("+") and not line.startswith("+++"):
            yield commit, path, line[1:]


def check_no_secrets_in_history(branch: str) -> list[str]:
    return sorted({f"commit {c}, {p}: {pattern}" for c, p, line in added_lines(branch)
                   for pattern in SECRET_PATTERNS if re.search(pattern, line)})


def check_no_personal_data(branch: str) -> list[str]:
    hits = set()
    for path in tracked_files():
        if path.name == Path(__file__).name:
            continue
        for pattern in PERSONAL_PATTERNS:
            if re.search(pattern, text_of(path)):
                hits.add(f"{path.relative_to(ROOT)}: {pattern}")
    for commit, path, line in added_lines(branch):
        if path.startswith("scripts/"):
            continue
        for pattern in PERSONAL_PATTERNS:
            if re.search(pattern, line):
                hits.add(f"commit {commit}, {path}: {pattern}")
    return sorted(hits)


def check_authors(branch: str, allowed: str | None = None) -> list[str]:
    """Commits whose author or committer address is neither GitHub's nor the one allowed."""
    accepted = allowed.lower() if allowed else None

    def fine(address: str) -> bool:
        return address.endswith(NOREPLY) or address == GITHUB_WEB or address.lower() == accepted

    lines = git("log", branch, "--format=%h %ae %ce").splitlines()
    return [line for line in lines if not all(fine(part) for part in line.split()[1:])]


def check_no_attribution(branch: str) -> list[str]:
    hits = []
    for entry in git("log", branch, "--format=%h%x00%B%x01").split("\x01"):
        if "\x00" not in entry:
            continue
        commit, message = entry.strip().split("\x00", 1)
        if any(re.search(pattern, message) for pattern in ATTRIBUTION_PATTERNS):
            hits.append(f"commit {commit}")
    return hits


def check_notebooks_without_outputs() -> list[str]:
    hits = []
    for path in sorted((ROOT / "notebooks").glob("*.ipynb")):
        notebook = nbformat.read(path, as_version=4)
        if any(cell.get("outputs") for cell in notebook.cells if cell.cell_type == "code"):
            hits.append(str(path.relative_to(ROOT)))
    return hits


def check_readme_links() -> list[str]:
    readme = text_of(ROOT / "README.md")
    links = re.findall(r"\]\(([^)#?]+)", readme)
    return [link for link in links if not link.startswith("http") and not (ROOT / link).exists()]


def main(branch: str = "HEAD", allowed_author: str | None = None) -> int:
    checks = [
        ("no .env or checkpoint files tracked", check_no_env_files()),
        ("no secrets in the working tree", check_no_secrets_in_tree()),
        ("no secrets in the history", check_no_secrets_in_history(branch)),
        ("no e-mail addresses or phone numbers", check_no_personal_data(branch)),
        ("every commit uses an accepted author address", check_authors(branch, allowed_author)),
        ("no tool attribution in commit messages", check_no_attribution(branch)),
        ("notebooks are stored without outputs", check_notebooks_without_outputs()),
        ("every README link resolves", check_readme_links()),
    ]
    failed = 0
    for name, problems in checks:
        print(f"{'PASS' if not problems else 'FAIL'}  {name}")
        for problem in problems[:8]:
            print(f"        {problem}")
        if len(problems) > 8:
            print(f"        ... and {len(problems) - 8} more")
        failed += bool(problems)
    print(f"\n{len(checks) - failed} of {len(checks)} checks passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("branch", nargs="?", default="HEAD")
    parser.add_argument(
        "--allow-author-email",
        metavar="ADDRESS",
        help="the author's own commit address, accepted besides GitHub's noreply addresses; "
        "given here so that it is never written into the repository",
    )
    arguments = parser.parse_args()
    sys.exit(main(arguments.branch, arguments.allow_author_email))
