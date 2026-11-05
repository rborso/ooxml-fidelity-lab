"""Corpus tests: split filtering and the frozen holdout digest."""

from __future__ import annotations

from pathlib import Path

from harness.corpus import Item, filter_split, holdout_digest


def item(doc_id, split, sha="a" * 64):
    return Item(
        id=doc_id,
        path=Path(f"/tmp/{doc_id}.docx"),
        cls="case_document",
        source="bugzilla",
        split=split,
        sha256=sha,
    )


ITEMS = [item("a", "dev"), item("b", "holdout"), item("c", "holdout")]


def test_filter_all_returns_everything():
    assert len(filter_split(ITEMS, "all")) == 3


def test_filter_dev():
    assert [i.id for i in filter_split(ITEMS, "dev")] == ["a"]


def test_filter_holdout():
    assert [i.id for i in filter_split(ITEMS, "holdout")] == ["b", "c"]


def test_holdout_digest_is_stable():
    assert holdout_digest(ITEMS) == holdout_digest(list(reversed(ITEMS)))


def test_holdout_digest_changes_when_a_document_changes():
    changed = [item("a", "dev"), item("b", "holdout", "b" * 64), item("c", "holdout")]
    assert holdout_digest(ITEMS) != holdout_digest(changed)


def test_holdout_digest_ignores_dev_documents():
    more_dev = ITEMS + [item("d", "dev")]
    assert holdout_digest(ITEMS) == holdout_digest(more_dev)
