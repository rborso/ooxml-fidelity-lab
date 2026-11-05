# OOXML Fidelity Lab

A versioned, corpus-driven differential harness that scores office-suite rendering and
round-trip fidelity against a pinned Microsoft Word — per document class, across new
documents and new releases.

It answers one question that currently can only be answered by running a pilot:
**will our documents work if we move off Microsoft Office?**

Status: **pre-M0**. Design and setup are complete; the harness has not been implemented.

---

## The problem in three lines

- "Will our documents work?" is unanswerable today without a pilot.
- A pilot is a political artifact — it can be cancelled, defunded, or orphaned. Denmark's
  Ministry of Digitization pilot died in a ministry reorganisation before its evaluation
  was ever completed, and the record now says "failed" when the truth is "unfinished".
- No neutral measurement exists. Vendors cannot credibly certify their own fidelity, and
  bug trackers hold anecdotes rather than scores.

This project is the measurement layer. It is modelled on **veraPDF** — publicly funded,
vendor-independent, permissively licensed, and now the authority for PDF/A — with one
essential difference: PDF/A is fully specified, so validation is possible. Word layout is
*not* specified, so this requires a differential oracle instead of a validator.

---

## What this is not

- Not an office suite. Not a fork of one.
- Not a migration playbook.
- Not a claim that 100% fidelity is reachable. It is not.
- Not a fix for the Microsoft monopoly. The binding constraints there are ecosystem
  coupling, bundled economics, coordination, and political durability. Fidelity is one of
  roughly five constraints, and it is the excuse more often than the cause.

See [GOALS.md](./GOALS.md) §7 for the honest claim.

---

## Documents

| File | Contents |
|---|---|
| [GOALS.md](./GOALS.md) | Problem, scope, success criteria, non-goals, risks |
| [DESIGN.md](./DESIGN.md) | Architecture, components, schema, scoring model, milestones |
| [SETUP.md](./SETUP.md) | Hardware, VM configuration, Word registry settings, renderer containers |

Read in that order.

---

## Repository layout

Only the harness, documentation, and configuration *templates* are public. All working
data — the corpus, rendered artifacts, run records, and local configuration — lives in
`private/`, which is gitignored.

```
ooxml-fidelity-lab/
├── README.md
├── GOALS.md
├── DESIGN.md
├── SETUP.md
├── config/                  # public templates only
│   ├── oracle.example.yaml
│   ├── renderers.example.yaml
│   └── tolerances.yaml
├── corpus/
│   ├── manifest.example.yaml
│   └── public/              # explicitly publishable fixtures only
├── harness/                 # the implementation (empty at pre-M0)
└── private/                 # GITIGNORED — nothing here is public
    ├── config/              # real configs: VM hashes, paths, digests
    ├── corpus/              # real documents
    ├── artifacts/           # reference + candidate PDFs, layout trees
    ├── runs/                # run store and provenance records
    ├── reports/             # drafts before publication
    └── vm/                  # VM build material, snapshots, licence notes
```

### Why the split is strict

The corpus is expected to include **real government and inter-agency documents**. Those
carry licence, confidentiality, and data-protection constraints that a public repository
cannot satisfy. Nothing enters `corpus/public/` until a redaction and licensing policy has
been written and applied.

Default rule: if you are unsure whether something is publishable, it goes in `private/`.

---

## Getting started

Prerequisites and full configuration: [SETUP.md](./SETUP.md).

The first milestone is deliberately narrow. Before anything else, verify that the oracle is
**deterministic**: render three documents twice each in Word, extract the layout trees, and
assert they are byte-identical. If that fails, nothing downstream is meaningful.

See SETUP.md §10. Do not build the framework before that gate is green.

---

## Disclaimer

Running the oracle requires a licensed Microsoft Word installation. The harness itself and
all published reference artifacts are open, so results are auditable without proprietary
software; Word is needed only to *add* corpus items, not to verify published scores. The
oracle is deliberately a swappable adapter so that no part of the analysis depends on
Microsoft's continued goodwill.

The reference build is pinned deliberately. Word 2019, Word 2021, Microsoft 365, Word for
Mac, and Word for the web are different rendering engines and produce different pages from
the same file. Any published score must name the reference build it was measured against.

---

## License

Not yet chosen. Intended to be a permissive license suitable for public-sector adoption
(Apache-2.0 or MPL-2.0), consistent with the veraPDF model. Until a LICENSE file exists,
all rights are reserved.
