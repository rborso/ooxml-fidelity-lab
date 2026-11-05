# private/ — working data, never published

This directory is gitignored except for this file. Everything that is not safe to publish
goes here.

## What belongs here

| Directory | Contents |
|---|---|
| `config/` | Real `oracle.yaml`, `renderers.yaml`, any local overrides — VM image hashes, paths, digests, font hashes |
| `corpus/` | Real documents. Assume confidential until proven otherwise |
| `artifacts/` | Reference and candidate PDFs, extracted layout trees |
| `runs/` | Run store (DuckDB), run records, provenance |
| `reports/` | Draft reports and scoreboards before publication |
| `vm/` | VM build material: unattend files, snapshots, activation/licence notes |

## The rule

**If you are unsure whether something is publishable, it goes here.**

The corpus is expected to contain real government and inter-agency documents. Those carry
licence, confidentiality, and data-protection constraints that a public repository cannot
satisfy. Nothing moves from here into `corpus/public/` until a redaction and licensing
policy exists and has been applied to that specific file.

## What does NOT belong here even though it is ignored

Ignored is not private in any strong sense — it is local. Do not put credentials in this
tree and assume they are protected; use a proper secret store. `.env` and key material are
ignored as a safety net, not as a policy.

## Suggested setup

```bash
mkdir -p private/{config,corpus,artifacts,runs,reports,vm}
cp config/oracle.example.yaml     private/config/oracle.yaml
cp config/renderers.example.yaml  private/config/renderers.yaml
chmod 700 private
```

Verify nothing leaked before pushing:

```bash
git status --ignored --short | head -50
git ls-files | grep -Ei '\.(docx|pdf|doc|odt)$'   # should be empty unless public fixtures
```
