# Governance — who owns the score

Neutrality is a governance property, not a technical one. A scoreboard owned by a vendor is
worthless to the people who need it, and a scoreboard owned by one individual has no
continuity.

This document is a decision framework, not a decision. The decision belongs to whoever
funds and hosts the work.

## Why it matters

The harness compares a commercial product against open alternatives. The first number
published will be attacked. Its credibility depends on three things that code cannot
provide:

1. **Independence** — the owner must not be a party whose product is being scored.
2. **Continuity** — the corpus, artefacts, and run history must outlive one person's
   attention span.
3. **Transparency** — method, corpus composition, and oracle build must be published
   alongside every number.

## Options

| Owner | Independence | Continuity | Notes |
|---|---|---|---|
| Foundation (Document Foundation, Open Preservation Foundation style) | high | high | Needs funding for corpus curation, which is the real cost |
| Public body (a digital-agency or standards body) | high | high | Slow, but the score becomes citable in procurement |
| University group | medium | medium | Good for method papers; funding cycles are short |
| Consortium of adopters | high | medium | Aligned incentives while everyone is migrating |
| Single vendor | low | medium | Disqualifying for a comparison against that vendor's competitor |
| Individual maintainer | medium | low | Fine to start; not fine to publish from |

## Minimum bar before publishing a number

- [ ] Corpus composition and version are public
- [ ] Oracle build is named and pinned
- [ ] The harness version and renderer digest are recorded in the run
- [ ] Known families are published with the score, not hidden in an appendix
- [ ] The holdout split was not used to tune the comparator
- [ ] Someone other than the author has reproduced one run

## Recommendation

Start as an individual maintainer with everything published and reproducible; move the
score to a foundation or public body before it is used in a procurement argument. The
artefacts that make the move possible are already the point of the project: a public corpus
description, published fixtures, and runs that carry their own provenance.

## Anti-patterns

- Publishing a single global "fidelity score". It hides the tail, and the tail is the point.
- Publishing a score without the family list. It invites "so it's 97%, good enough".
- Letting the vendor whose product scores well fund the harness.
- Letting the vendor whose product scores badly review the method before publication.
