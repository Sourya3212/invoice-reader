import tempfile
from pathlib import Path

import pymupdf

from invoice_reader.ingest import plain_letters, read_text


def test_ligature_characters_become_plain_letters():
    assert plain_letters("Oﬃce, Muﬃn, ﬁle, ﬂour") == "Office, Muffin, file, flour"


def test_reading_a_pdf_spells_out_ligatures():
    # The generated invoices store "ffi" as one character, as many real PDFs do. Reading must give plain letters.
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "invoice.pdf"
        doc = pymupdf.open()
        doc.new_page().insert_htmlbox(pymupdf.Rect(50, 50, 550, 200),
                                      "<p>Brightline Office Supply, 15 Mill Road, Hamburg. Muffin tray x 2</p>")
        doc.save(path)
        with pymupdf.open(path) as pdf:
            assert "ﬃ" in "".join(page.get_text() for page in pdf)  # the PDF really holds the ligature
        text, method = read_text(path)
        assert method == "pdf-text" and "Office Supply" in text and "Muffin" in text and "ﬃ" not in text
