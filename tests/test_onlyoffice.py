"""OnlyOffice adapter contract: it must either render or say precisely why not."""

from __future__ import annotations

import pytest

from harness.render import RenderError, onlyoffice_available, render_onlyoffice


def test_unconfigured_reports_the_missing_piece():
    available, reason = onlyoffice_available(None)
    assert available is False
    assert "ONLYOFFICE_URL" in reason
    assert "documentserver" in reason


def test_unreachable_reports_the_address():
    available, reason = onlyoffice_available("http://127.0.0.1:1")
    assert available is False
    assert "unreachable" in reason


def test_render_raises_a_precise_error_when_unconfigured(tmp_path):
    doc = tmp_path / "a.docx"
    doc.write_bytes(b"not really a docx")
    with pytest.raises(RenderError) as excinfo:
        render_onlyoffice(doc, tmp_path / "out", url=None)
    assert "ONLYOFFICE_URL" in str(excinfo.value)
