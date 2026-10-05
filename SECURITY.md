# Security Policy

This repository is an educational project (LangGraph literate-programming
notebook series). It processes only synthetic, fictional data — no real
customer, personal, or company data — and runs no production service.

## Scope

In scope: the code, notebooks, fixtures, and CI configuration in this
repository. Out of scope: anything about LangGraph, LangChain, or Ollama
themselves — report those to their respective maintainers.

## Reporting a vulnerability or an exposed secret

If you find a genuine security issue — for example a credential
accidentally committed, a dependency with a known critical CVE pulled in
by this repo, or a way the notebook runner's `expected_exception` contract
could be bypassed to hide a real failure — please open a private report via
[GitHub's "Report a vulnerability" feature](../../security/advisories/new)
on this repository rather than a public issue.

If you spot a committed credential: please still flag it even though this
repo intends to hold none. On confirmation, the credential is rotated
immediately — deleting it from the current file or from history alone is
not treated as sufficient remediation.

## What this policy does not cover

This is a student project maintained by one person in their spare time.
There is no bug bounty, no SLA, and no guarantee of response time — but
reports are read and taken seriously.
