"""Custom-renderer configuration tests. No build tree is required."""

from __future__ import annotations

import pytest

from harness import render
from harness.render import RenderError


def test_missing_configuration_names_both_backends(monkeypatch, tmp_path):
    monkeypatch.setattr(render, "CUSTOM_IMAGE", None)
    monkeypatch.setattr(render, "CUSTOM_SOFFICE", None)
    doc = tmp_path / "a.docx"
    doc.write_bytes(b"not a docx")
    with pytest.raises(RenderError) as excinfo:
        render.render_custom(doc, tmp_path / "out")
    message = str(excinfo.value)
    assert "CUSTOM_SOFFICE" in message
    assert "CUSTOM_IMAGE" in message


def test_binary_takes_precedence_over_image(monkeypatch, tmp_path):
    """A built tree is used when both are set: it is the more specific choice."""
    calls = {}

    def fake_soffice(binary, docx, out_dir, timeout=180):
        calls["binary"] = binary
        return out_dir / "out.pdf"

    monkeypatch.setattr(render, "CUSTOM_SOFFICE", "/build/soffice")
    monkeypatch.setattr(render, "CUSTOM_IMAGE", "img@sha256:abc")
    monkeypatch.setattr(render, "render_soffice", fake_soffice)
    render.render_custom(tmp_path / "a.docx", tmp_path / "out")
    assert calls["binary"] == "/build/soffice"


def test_unbuildable_binary_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(render, "CUSTOM_SOFFICE", str(tmp_path / "nope" / "soffice"))
    monkeypatch.setattr(render, "CUSTOM_IMAGE", None)
    doc = tmp_path / "a.docx"
    doc.write_bytes(b"not a docx")
    with pytest.raises((RenderError, OSError)):
        render.render_custom(doc, tmp_path / "out")
