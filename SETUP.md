# OOXML Fidelity Lab — Setup & Configuration

Companion: [GOALS.md](./GOALS.md) · [DESIGN.md](./DESIGN.md)

Everything below is the concrete "what to buy, how to configure it" for M0/M1.
The single requirement that shapes all of it: **the oracle must be offline, pinnable,
deterministic, and complete.** Every choice follows from that.

---

## 0. What you already have

| Item | Status | Note |
|---|---|---|
| Office Professional Plus 2019 | have | Volume SKU — confirm the licence is yours, not an employer's |
| Windows licence | have | Which edition/version? Record it; it becomes part of the image hash |
| Host machines for VMs | have | Needs to support snapshotting + offline networking |

**Office 2019 caveat:** extended support ended 14 Oct 2025. Fine — arguably good — for a
prototype oracle, because a frozen build can't drift. But you are pinning a 2019 rendering
engine, and your target population probably runs M365. Treat 2019 as the *pipeline prover*,
not the published reference. Survey the real population before M2.

---

## 1. Host topology

```
Linux host (KVM/QEMU + libvirt)
│
├── VM: oracle-win  ── Windows + Office 2019
│      network: NONE (host-only after build; no NIC on the test snapshot)
│      I/O: shared folder  ──▶  C:\work\in   /   C:\work\out
│      one render job at a time (Word COM is single-threaded)
│
├── Containers: renderers
│      collabora/code@sha256:…        (Collabora Online)
│      libreoffice:…@sha256:…         (LibreOffice desktop, CLI convert)
│      onlyoffice/documentserver@…    (OnlyOffice)
│
└── Host processes
       harness (Python 3.12)
       run store (DuckDB)
       corpus (git-lfs) + artifacts (plain dir)
```

Why KVM on Linux rather than VirtualBox: scriptable snapshots, digest-able images, clean
offline networking, and no host reboot for updates. If your comfort zone is VMware/Hyper-V,
that's fine — the requirement is snapshot + no-NIC, not the hypervisor.

---

## 2. Hardware sizing

| Role | Spec | Notes |
|---|---|---|
| Oracle VM | 4 vCPU, 8 GB RAM, 80 GB disk | Word + Windows. Rendering is single-threaded — extra cores don't help one job |
| Oracle VM × N | one VM per parallel worker | Do **not** run concurrent jobs on one VM; do **not** clone one activation |
| Renderer host | 8 vCPU, 16 GB RAM | OnlyOffice Document Server is heavy (PG + RabbitMQ + Redis ~4 GB) |
| Storage | 200 GB working | 2,000 docs × ~5 render variants × 1–3 MB PDF + JSON layout trees |
| Backup | 500 GB | Run records + reference artifacts are the product |

Scaling throughput means more VMs (more licences), not more threads.

---

## 3. Windows VM provisioning

Build it once, snapshot it, never touch it again.

```powershell
# Locale and region — must be identical to the document population's authoring locale.
# Paper size follows locale: en-US defaults to Letter, which silently changes pagination.
Set-WinSystemLocale  -SystemLocale da-DK      # match your population
Set-Culture          -CultureInfo  da-DK
Set-WinUILanguageOverride -Language da-DK
Set-TimeZone         -Id "Romance Standard Time"

# Strip everything that can change output
powercfg -h off
Set-Service wuauserv -StartupType Disabled
Stop-Service wuauserv

# Do not let Defender or the indexer touch the work directory
Add-MpPreference -ExclusionPath 'C:\work'
Set-Service WSearch -StartupType Disabled
Stop-Service WSearch

# No consumer features, no OneDrive, no Store autostart
Get-AppxPackage *OneDrive* | Remove-AppxPackage
```

**Then:** set display to a fixed resolution, disable screensaver and sleep, set power plan
to High Performance, remove all network adapters from the test snapshot.

Record and store: Windows edition + build, image SHA-256, Office build (`16.0.xxxxx`),
font directory hash.

---

## 4. Word configuration

### 4.1 Launch flags

Always start Word with `/a`:

```
WINWORD.EXE /a
```

`/a` loads Word without add-ins, global templates, or automatic macros. It is the single
highest-value determinism setting — it eliminates a whole class of "why did this change"
mysteries.

### 4.2 Trust Center — required, or automation silently misbehaves

Files arriving from a network path open in Protected View and can refuse automation.
Set a trusted local location and disable Protected View:

```
HKLM\SOFTWARE\Microsoft\Office\16.0\Word\Security\Trusted Locations\Location1
    Path              = C:\work\
    AllowSubfolders   = 1 (DWORD)
    Description       = fidelity-lab

HKCU\SOFTWARE\Microsoft\Office\16.0\Word\Security\ProtectedView
    DisableInternetFilesInPV   = 1
    DisableUnsafeLocationsInPV = 1
    DisableAttachmentsInPV     = 1
```

### 4.3 Determinism settings

Set these once in the UI, then **export the registry branches to `.reg` files and treat
them as part of the image**. Don't hand-maintain key names; capture what the UI produces.

Required choices:

- **Default printer:** install a fixed driver (Microsoft Print to PDF is fine), set it as
  default, and never change it. Set
  `HKCU\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Windows\LegacyDefaultPrinterMode = 1`
  so Windows respects your choice instead of "last used".
- **Disable hardware graphics acceleration:**
  `HKCU\SOFTWARE\Microsoft\Office\16.0\Common\Graphics\DisableHardwareAcceleration = 1`
- **Turn off field updating before print/export** (dates and page fields otherwise make
  output non-reproducible).
- **Pin the track-changes display state.** PDF export honours the "print markup" setting,
  so a document with revisions will export differently depending on a UI toggle. Set it
  explicitly per document in the agent (see 6), not by hand.
- **Turn off AutoRecover / background save.**
- **Disable "show background repagination" only if you observe it affecting output** —
  normally leave it alone.

### 4.4 Fonts

**The oracle gets the real fonts. The renderers get the metric-compatible clones.**

That asymmetry is the whole point of the test. Oracle: Calibri, Cambria, Georgia, Arial,
Times New Roman — whatever Office 2019 installs, plus any corporate fonts your document
population actually uses. Renderers: Carlito (Calibri), Caladea (Cambria), Gelasio
(Georgia), Liberation (Arial/Times). If you install the real fonts on the renderer you're
testing a machine nobody has.

Record `sha256` of the font directory in both places.

### 4.5 Activation

Unactivated Office enters reduced-functionality mode and will corrupt reference output.
Verify activation, and record the licence state in the run record.

---

## 5. Offline file transfer

No network on the test VM. Use a shared folder (virtiofs / 9p) mounted as `C:\work`,
because you need a **queue**, not an API:

```
C:\work\in\<jobid>\document.docx
C:\work\in\<jobid>\job.json
C:\work\out\<jobid>\document.pdf
C:\work\out\<jobid>\result.json
C:\work\out\<jobid>\DONE
```

The host writes a job, the in-VM agent polls, renders, writes the artifacts and a `DONE`
marker. Simple, debuggable, and it survives reboots without a network stack.

---

## 6. The in-VM agent

A small Python script using `pywin32`, running inside the VM as a scheduled task or
service. One document, one fresh Word process, one PDF.

```python
import json, sys, pathlib
import win32com.client as win32

def render(src: pathlib.Path, dst: pathlib.Path):
    word = win32.gencache.EnsureDispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    word.Options.UpdateFieldsBeforePrint = False
    word.Options.UpdateLinksAtOpen = False
    try:
        doc = word.Documents.Open(
            FileName=str(src), ReadOnly=True, AddToRecentFiles=False,
            Visible=False, ConfirmConversions=False,
        )
        # Pin the revision display state — it changes the exported PDF.
        doc.ActiveWindow.View.ShowRevisionsAndComments = True
        doc.ActiveWindow.View.RevisionsView = 0        # wdRevisionsViewFinal
        word.Options.PrintRevisions = True

        doc.ExportAsFixedFormat(
            OutputFileName=str(dst),
            ExportFormat=17,          # wdExportFormatPDF
            OpenAfterExport=False,
            OptimizeFor=0,            # wdExportOptimizeForPrint
            Range=0,                  # wdExportAllDocument
            Item=0,                   # wdExportDocumentContent
            IncludeDocProps=True,
            KeepIRM=True,
            CreateBookmarks=0,
            DocStructureTags=True,
            BitmapMissingFonts=True,
            UseISO19005_1=False,
        )
        doc.Close(SaveChanges=0)
    finally:
        word.Quit()

if __name__ == "__main__":
    render(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))
```

Notes that matter:

- `OptimizeFor=0` (print) rather than on-screen — you want the printed layout.
- A **fresh Word process per document**. Word leaks and carries state between documents;
  reuse is the most common source of non-reproducible output.
- Never call `Save()`. The oracle only ever converts.

---

## 7. Renderer containers

Pin every image by digest. A floating tag destroys comparability across runs.

The commands below use **podman**, which is what is installed on the lab host (rootless,
5.8.2, verified). Docker is not present; if you install it, the same OCI images and flags
apply — just swap the binary. Rootless podman is preferable for a harness that runs
untrusted documents through a converter.

### Verified: Collabora Online's engine as a batch converter

LibreOffice is **not packaged for Rocky Linux 10** (`dnf search libreoffice` returns
nothing) and no flatpak is installed, so renderers run in containers.

The `collabora/code` image is the same engine Nextcloud ships by default. But its image is
Nix-built and contains **no shell at all**, so the usual `soffice` wrapper script cannot
execute (its `/bin/sh` interpreter is absent — you get a misleading "No such file or
directory"). Invoke the real binary directly:

```bash
podman run --rm --user 0 -e HOME=/tmp \
  -v "$PWD/in:/in:Z" -v "$PWD/out:/out:Z" \
  --entrypoint /opt/collaboraoffice/program/soffice.bin \
  collabora/code:<version>@sha256:<digest> \
  --headless --norestore --convert-to pdf --outdir /out /in/document.docx
```

Verified on the lab host: `Producer: Collabora Office 26.04.5.2 (X86_64)`.

Note the binary path is `/opt/collaboraoffice/program/soffice.bin` — Collabora ships its own
branded build, not TDF LibreOffice. That is the correct choice when the deployment target is
Nextcloud + Collabora, because it is the build and font set your users actually get.

### Verified font gap

The image ships Carlito (Calibri metric clone), Caladea (Cambria), Liberation
(Arial/Times), DejaVu and a Noto subset. It does **not** ship Georgia, Calibri, Cambria, or
Gelasio.

A paragraph requesting **Georgia** was substituted with **NotoSerif** — the generic serif
fallback, *not* a metric-compatible clone — which changes line breaks and pagination.

This reproduces, empirically, the failure that broke the Danish pilot's templates. It is a
configuration problem, not a code defect: either add Gelasio (metric-compatible Georgia) to
the renderer image, or remove Georgia from the templates. Do it before blaming the engine.

### Other renderers

```bash
# OnlyOffice — heavier; the all-in-one image bundles PG, RabbitMQ and Redis
podman run --rm -d -p 8080:80 onlyoffice/documentserver:<version>@sha256:<digest>

# Collabora Online as a service (only needed for WOPI/embedding fidelity tests;
# batch conversion uses the soffice.bin path above)
podman run --rm -d -p 9980:9980 --cap-add SYS_ADMIN \
  collabora/code:<version>@sha256:<digest>
```

Each renderer is an adapter behind:

```python
render(docx_path) -> pdf_path
convert(docx_path) -> docx_path      # for round-trip; exposes x2t separately
```

`x2t` (from the OnlyOffice `core` repo) deserves its own adapter: it converts
OOXML↔ODF↔bin without rendering, which isolates conversion loss from layout loss.

---

## 8. Harness environment

```bash
python3.12 -m venv .venv
.venv/bin/pip install \
  pymupdf lxml python-docx pydantic pyyaml typer \
  duckdb pikepdf imagehash pillow pytest
```

| Package | Use |
|---|---|
| `pymupdf` | PDF → span/bbox layout tree |
| `lxml` | DOCX XML, round-trip semantic diff, rsid normalisation |
| `python-docx` | synthetic single-construct documents |
| `pikepdf` | strip PDF CreationDate/ModDate before hashing |
| `pydantic` | validate corpus manifest and run records |
| `duckdb` | run store |
| `pywin32` | inside the VM only |

**PDF byte hashes will differ between runs** because of embedded timestamps. Either hash
the extracted layout tree (preferred) or scrub metadata with `pikepdf` first. Publishing a
byte-hash determinism test without scrubbing will fail for a boring reason.

---

## 9. Configuration files

Only the templates are public. The live files live in `private/config/` (gitignored),
because they contain VM image hashes, container digests, local paths, and font hashes.

```bash
mkdir -p private/{config,corpus,artifacts,runs,reports,vm}
cp config/oracle.example.yaml    private/config/oracle.yaml
cp config/renderers.example.yaml private/config/renderers.yaml
```

`config/tolerances.yaml` is public as-is — it carries scoring policy, not machine data.

### `private/config/oracle.yaml`

```yaml
oracle:
  name: word-desktop-2019
  vm:
    image_sha256: "…"          # bumped every time the VM changes
    hypervisor: kvm
    network: none
  word:
    version: "16.0.10388"
    channel: perpetual-2019
    activated: true
    launch_flags: ["/a"]
  windows:
    edition: "Windows 10 Pro"
    build: "19045"
    locale: da-DK
    paper: A4
  printer:
    driver: "Microsoft Print to PDF"
    name: "Microsoft Print to PDF"
  fonts:
    directory_sha256: "…"
  determinism:
    double_render_required: true
    export: pdf
    export_optimize_for: print
```

### `private/config/renderers.yaml`

```yaml
renderers:
  - name: libreoffice
    image: "libreoffice:24.8"
    digest: "sha256:…"
    adapter: soffice
  - name: collabora-online
    image: "collabora/code:24.04"
    digest: "sha256:…"
    adapter: coolwsd
  - name: onlyoffice
    image: "onlyoffice/documentserver:8.2"
    digest: "sha256:…"
    adapter: onlyoffice
  - name: x2t
    image: "…"
    digest: "sha256:…"
    adapter: convert_only
```

### `config/tolerances.yaml`

```yaml
tiers:
  t1:
    require_same_page_count: true
    require_same_line_count: true
    line_break_match_ratio: 1.0
  t2:
    median_pt_max: 1.0
    p95_pt_max: 4.0
    ignore_regions: []          # e.g. footers with live dates
  t3:
    ssim_min: 0.95              # informational only; never gates a score
weights:
  t0_failure: caps_score_at_zero
  document_class:
    case_document: 1.0
    template: 1.5
    annex: 0.4
```

### `private/corpus/manifest.yaml`

```yaml
corpus_version: 1
items:
  - id: dk-case-0001
    sha256: "…"
    path: items/dk-case-0001.docx
    class: case_document
    source: records-request
    authored_in: word-2019
    tags: [tables, numbering, track_changes]
    licence: internal-only
    split: dev
```

---

## 10. Determinism verification (the go/no-go gate)

Do this before anything else. If it fails, stop and fix it — nothing downstream means
anything.

1. Pick 3 documents: one trivial, one table-heavy, one with tracked changes.
2. Render each **twice** through the oracle.
3. Extract layout trees from both PDFs.
4. Assert byte-identical layout trees.
5. Repeat with a **fresh Word process** vs. a reused one. Note the difference; you must
   use fresh processes.
6. Change the default printer, re-render, diff. Record how much moves. If it moves a lot,
   you have found why nobody can reproduce office rendering, and printer pinning is now
   load-bearing.
7. Repeat 1–4 for each renderer container.

Pass condition: identical layout trees across repeated renders, for every document, in
every renderer, with the same image digests.

---

## 11. Procurement checklist

| Item | Why | Status |
|---|---|---|
| Office licence for the oracle VM (2019 or M365) | Only route to reference PDFs | have (2019) |
| Windows licence for the VM | Same | have |
| Hypervisor host with 16 GB+ and snapshot support | Run the VM | have |
| Linux host, 8 vCPU / 16 GB / 200 GB | Renderers + harness | ? |
| Backup volume, 500 GB | Runtime records are the product | ? |
| M365 licence, **if** the population runs M365 | Correct reference build | decide after survey |
| Legal review: licence provenance, reverse-engineering scope | Publishability | ? |
| Corpus licence/redaction policy | Gates the corpus, gates publication | ? |

---

## 12. Build order

1. VM + Windows + Office, snapshot, record hashes
2. Registry/config capture as `.reg` files, committed
3. In-VM agent + file queue
4. Determinism gate (§10) — **do not proceed until green**
5. PDF → layout tree extractor + T0/T1 comparators
6. One renderer container, 20 documents, one Markdown report
7. Then, and only then, scale the corpus and add T2/T3

The failure mode to avoid: building the full framework before proving determinism. Twenty
documents and one honest report will tell you whether the scoring model is right. Two
thousand documents and a beautiful pipeline that scores the wrong thing is the expensive
way to learn the same lesson.
