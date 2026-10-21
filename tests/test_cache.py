import tempfile
from pathlib import Path

import pymupdf

import invoice_reader.pipeline as pipeline
from invoice_reader.pipeline import _text


def _pdf(path: Path, text: str) -> None:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), text)
    doc.save(path)


def test_same_name_different_files_do_not_share_cached_text():
    # Two test sets both contain a doc_002.pdf. A cache keyed by name once served one set's text for the other.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "set_a").mkdir()
        (root / "set_b").mkdir()
        _pdf(root / "set_a" / "doc_002.pdf", "Harbor and Finch Consulting, invoice SO-47696, total 5,106.51")
        _pdf(root / "set_b" / "doc_002.pdf", "The Lunch Box, order R-03048, amount paid 3,895.79")
        cache = root / "_text"
        text_a, _ = _text(root / "set_a" / "doc_002.pdf", cache)
        text_b, _ = _text(root / "set_b" / "doc_002.pdf", cache)
        assert "Harbor and Finch" in text_a
        assert "The Lunch Box" in text_b and "Harbor" not in text_b


def test_changing_the_reading_code_reads_the_text_again():
    # Text cached by older reading code must not hide a fix to that code (like spelling out ligatures).
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _pdf(root / "doc_001.pdf", "Harbor and Finch Consulting, invoice SO-47696, total 5,106.51")
        cache = root / "_text"
        _text(root / "doc_001.pdf", cache)
        before = pipeline._READER
        try:
            pipeline._READER = before + b"# a change to the reading code"
            _text(root / "doc_001.pdf", cache)
        finally:
            pipeline._READER = before
        assert len(list(cache.glob("*.txt"))) == 2
