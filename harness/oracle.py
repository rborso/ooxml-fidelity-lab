"""Host-side driver for the Windows oracle VM.

Batch, not per-document: the VM boots once, drains a queue, and powers itself
off. That keeps the render window fully offline and makes completion a power
state rather than a network signal.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
BATCH_SCRIPT = HERE.parent / "scripts" / "host" / "oracle-batch.sh"


class OracleError(RuntimeError):
    pass


class WindowsOracle:
    def __init__(self, domain: str = "win11-0", timeout: int = 900, workdir: Path | None = None):
        self.domain = domain
        self.timeout = timeout
        self.workdir = workdir

    def render_batch(self, docs: dict[str, Path], out_dir: Path) -> dict[str, Path]:
        """Render docs through the VM. Returns {jobid: pdf_path} for successes.

        Raises OracleError if the batch could not run at all. Individual document
        failures are reported, not raised: a hung document must not lose the
        rest of the batch.
        """
        out_dir = out_dir.resolve()
        stage = (self.workdir or out_dir.parent / "stage").resolve()
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir(parents=True, exist_ok=True)

        for job_id, docx in docs.items():
            job = stage / job_id
            job.mkdir(parents=True, exist_ok=True)
            # Preserve the extension: a legacy .doc renamed to .docx would be
            # parsed as OOXML and fail for the wrong reason.
            shutil.copy2(docx, job / f"document{docx.suffix.lower()}")

        env = dict(os.environ, ORACLE_BOOT_TIMEOUT=str(self.timeout))
        proc = subprocess.run(
            ["bash", str(BATCH_SCRIPT), str(stage), str(out_dir), self.domain],
            capture_output=True,
            text=True,
            env=env,
        )
        if proc.returncode not in (0, 3):
            raise OracleError(
                f"oracle batch failed (exit {proc.returncode})\n"
                f"{proc.stderr[-1500:]}"
            )

        rendered: dict[str, Path] = {}
        for job_id in docs:
            pdf = out_dir / job_id / "document.pdf"
            if pdf.exists() and (out_dir / job_id / "DONE").exists():
                rendered[job_id] = pdf
        self.last_stderr = proc.stderr
        return rendered

    def results(self, out_dir: Path) -> dict[str, dict]:
        """Per-document result.json, including failures."""
        found: dict[str, dict] = {}
        for result in sorted(out_dir.glob("*/result.json")):
            try:
                found[result.parent.name] = json.loads(result.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                continue
        return found
