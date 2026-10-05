# ADR 0006: What may go into the public repository

**Status:** Accepted (20 August 2026, revised 4 October 2026)

## Context

The repository is published on GitHub as coursework and as a portfolio
piece. It contains sample data, code, notebooks and CI configuration.

## Decision

The repository contains only synthetic, non-confidential material:

- no API keys, tokens, secrets or `.env` files;
- no real personal, customer or company data;
- no private correspondence and no names of people other than the author;
- no proprietary standard texts;
- no tool attribution in commit messages: the author is the only
  contributor.

The first push is a deliberate step taken by the author after the
pre-publication check (`scripts/prepublication_check.py`), never an automated
one.

## Alternatives considered

- **Private repository, made public later:** only postpones the check.
- **Automatic push on green CI:** a green build says nothing about whether
  the content is fit for publication.

## Consequences

- GitHub secret scanning and push protection are an extra layer, not a
  substitute for the check. If a secret is ever exposed, it is rotated;
  deleting it from the history is not enough.
- Commit metadata is public too, so commits use the author's GitHub noreply
  address.
