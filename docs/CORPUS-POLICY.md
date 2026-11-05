# Corpus policy — licence, redaction, publication

The corpus is the project's most valuable asset and its biggest legal exposure. This
policy exists so that "can we include this document?" has an answer before the question is
asked in a meeting.

## 1. Three tiers of material

| Tier | What | Where it can live |
|---|---|---|
| **Public** | Synthetic documents we generate, and documents explicitly licensed for redistribution | Repository, published reports |
| **Internal** | Tracker attachments, documents under an unknown or permissive-but-unverified licence | `private/corpus/`, site visible on the internal network only |
| **Restricted** | Government or client documents with confidentiality obligations | `private/corpus/`, never published, never shared outside the lab |

Default is **Restricted**. Material moves up a tier only by an explicit decision, recorded
in the manifest.

## 2. Rules

1. **No document enters the corpus without a `licence` field.** `make check --strict` fails
   otherwise.
2. **Redaction is applied before ingestion, not after.** A redacted document is re-hashed;
   the original is not kept in the repository.
3. **Published scores name their corpus version and composition.** A score without a
   corpus description is not a result.
4. **Nothing is published from the Restricted tier** — not the document, not a rendered
   page, not a quoted paragraph.
5. **Tracker attachments are Internal until proven otherwise.** A bug report is not a
   licence.

## 3. Publication checklist

Before any corpus artefact leaves the lab:

- [ ] Every item carries a resolvable `licence`
- [ ] Every item is in the Public tier
- [ ] Hashes in the manifest match the files
- [ ] Rendered pages reviewed for incidental personal data
- [ ] Corpus composition and version published alongside the scores

## 4. What "publishable" means here

The scores can be public while the corpus is not. That is the normal case: publish the
method, the aggregate numbers, the failure families, and the synthetic fixtures; keep the
documents themselves internal. Anyone who wants to verify can run the harness against their
own corpus.

## 5. Open items

- Real government documents need a data-processing agreement before they enter the
  Restricted tier.
- The safe-subset authoring guide (`AUTHORING.md`) tells authors how to avoid the
  constructs that fail, which is often cheaper than fixing the renderer.
