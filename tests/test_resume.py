import json
import tempfile
from pathlib import Path

import pymupdf

from invoice_reader.pipeline import run
from invoice_reader.schema import Invoice


def test_resume_retries_failures_and_rechecks_kept_answers():
    # If Ollama stops mid-run, the remaining documents are saved as failed: --resume must retry them, not keep them.
    # Answers it keeps get today's checks, so a new check applies without calling the AI again.
    with tempfile.TemporaryDirectory() as d:
        docs, out = Path(d) / "docs", Path(d) / "out"
        docs.mkdir()
        (out / "pred").mkdir(parents=True)
        for name in ("doc_001", "doc_002"):
            pdf = pymupdf.open()
            pdf.new_page().insert_text((72, 72), f"Harbor and Finch Consulting, invoice {name}, total 10.00")
            pdf.save(docs / f"{name}.pdf")
        base = {"file": "", "method": "pdf-text", "backend": "rules", "model": None, "issues": [], "invoice": None}
        (out / "pred" / "doc_001.json").write_text(json.dumps(
            {**base, "doc_id": "doc_001", "seconds": 0.0, "error": "ConnectError: connection refused"}))
        saved = Invoice(vendor_name="Harbor and Finch Consulting", invoice_number="1", issue_date="2026-07-08",
                        currency="USD", subtotal=10.0, total=12.0)  # doesn't add up, but was saved with no issues
        (out / "pred" / "doc_002.json").write_text(json.dumps(
            {**base, "doc_id": "doc_002", "seconds": 99.0, "error": None, "invoice": saved.model_dump()}))
        rows = {r["doc_id"]: r for r in run(str(docs), str(out), backend="rules", resume=True)}
        assert rows["doc_001"]["error"] is None  # the failed one was read again
        assert rows["doc_002"]["seconds"] == 99.0  # the saved answer was kept...
        assert any("total is 12.00" in i for i in rows["doc_002"]["issues"])  # ...and checked again
