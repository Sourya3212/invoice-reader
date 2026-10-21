"""Score an extractor's answers against the correct answers, field by field.

Text fields are compared after trimming and ignoring case, as a spreadsheet search would: "Oﬃce" spelled with a
ligature character is not "Office". Invoice numbers ignore spaces; money must match to the cent; dates must match
exactly. A document is "fully correct" when every key field is right.
The review-queue numbers show whether the checks catch the wrong documents.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from .pipeline import load_preds, load_truth
from .schema import KEY_FIELDS, Invoice

MONEY = {"subtotal", "discount", "shipping", "tax", "total"}
FIELDS = KEY_FIELDS + ["discount", "shipping"]


def same(field: str, truth, pred) -> bool:
    if field in MONEY:
        return pred is not None and abs(float(truth or 0) - float(pred or 0)) <= 0.01
    if truth in (None, "") and pred in (None, ""):
        return True
    if truth in (None, "") or pred in (None, ""):
        return False
    if field == "invoice_number":
        return re.sub(r"\s", "", str(truth)).upper() == re.sub(r"\s", "", str(pred)).upper()
    # lower(), not casefold(): casefold() turns the ligature "ﬃ" into "ffi" and once hid exactly that error.
    return str(truth).strip().lower() == str(pred).strip().lower()


def item_scores(truth: Invoice, pred: dict | None) -> tuple[int, int, int]:
    """(matched, truth_items, predicted_items): an item matches on amount (to the cent) and quantity."""
    t = [(round(i.amount, 2), i.quantity) for i in truth.line_items]
    p = [(round(float(i["amount"]), 2), float(i["quantity"])) for i in (pred or {}).get("line_items", [])]
    matched, pool = 0, list(p)
    for a, q in t:
        hit = next((x for x in pool if abs(x[0] - a) <= 0.01 and abs(x[1] - q) < 1e-6), None)
        if hit:
            matched += 1
            pool.remove(hit)
    return matched, len(t), len(p)


def evaluate(pred_dir: str, truth_dir: str, manifest: str | None = None) -> dict:
    preds, truth = load_preds(pred_dir), load_truth(truth_dir)
    kinds = {}
    if manifest and Path(manifest).exists():
        kinds = {r["doc_id"]: ("scan" if r["scanned"] == "True" else "digital")
                 for r in csv.DictReader(open(manifest, encoding="utf-8"))}
    per_doc = []
    for doc_id, t in sorted(truth.items()):
        rec = preds.get(doc_id)
        inv = (rec or {}).get("invoice")
        fields = {f: same(f, getattr(t, f), (inv or {}).get(f)) for f in FIELDS}
        m, nt, np_ = item_scores(t, inv)
        fully = all(fields[f] for f in KEY_FIELDS)
        per_doc.append({"doc_id": doc_id, "kind": kinds.get(doc_id, "?"), "fields": fields,
                        "fully_correct": fully,
                        # everything right, line items included: only these count as false alarms when flagged
                        "all_right": fully and m == nt == np_,
                        "items": (m, nt, np_), "flagged": bool((rec or {}).get("issues", ["missing"])),
                        "seconds": (rec or {}).get("seconds")})

    def rate(xs):
        xs = list(xs)
        return round(100 * sum(xs) / len(xs), 1) if xs else None

    groups = {"all": per_doc, "digital": [d for d in per_doc if d["kind"] == "digital"],
              "scan": [d for d in per_doc if d["kind"] == "scan"]}
    res = {"documents": len(per_doc), "groups": {}}
    for g, ds in groups.items():
        if not ds:
            continue
        m = sum(d["items"][0] for d in ds)
        nt = sum(d["items"][1] for d in ds)
        np_ = sum(d["items"][2] for d in ds)
        res["groups"][g] = {
            "n": len(ds),
            "field_accuracy": {f: rate(d["fields"][f] for d in ds) for f in FIELDS},
            "fully_correct": rate(d["fully_correct"] for d in ds),
            "item_recall": round(100 * m / nt, 1) if nt else None,
            "item_precision": round(100 * m / np_, 1) if np_ else None,
        }
    wrong = [d for d in per_doc if not d["fully_correct"]]
    flagged = [d for d in per_doc if d["flagged"]]
    res["review_queue"] = {
        "wrong_documents": len(wrong),
        "wrong_and_flagged": sum(d["flagged"] for d in wrong),
        "flagged": len(flagged),
        "flagged_key_fields_right": sum(d["fully_correct"] for d in flagged),
        "false_alarms": sum(d["all_right"] for d in flagged),  # flagged although everything was right
        "wrong_but_passed": [d["doc_id"] for d in wrong if not d["flagged"]],
        # only meaningful when the extractor reads line items at all (the rules baseline does not)
        "item_errors_passed": ([d["doc_id"] for d in per_doc if d["fully_correct"] and not d["all_right"]
                                and not d["flagged"]] if any(d["items"][2] for d in per_doc) else None),
    }
    secs = [d["seconds"] for d in per_doc if d["seconds"] is not None]
    res["seconds_per_document"] = round(sum(secs) / len(secs), 2) if secs else None
    res["per_doc"] = per_doc
    return res


def report_md(res: dict, title: str) -> str:
    g = res["groups"]
    cols = [k for k in ("all", "digital", "scan") if k in g]
    out = [f"# {title}", "", f"{res['documents']} documents. Accuracy in % (money to the cent, dates exact).", "",
           "| Field | " + " | ".join(f"{c} (n={g[c]['n']})" for c in cols) + " |",
           "|---|" + "---|" * len(cols)]
    for f in FIELDS:
        out.append(f"| {f} | " + " | ".join(str(g[c]["field_accuracy"][f]) for c in cols) + " |")
    out.append("| **all key fields right** | " + " | ".join(f"**{g[c]['fully_correct']}**" for c in cols) + " |")
    out.append("| line items found (recall) | " + " | ".join(str(g[c]["item_recall"]) for c in cols) + " |")
    out.append("| line items right (precision) | " + " | ".join(str(g[c]["item_precision"]) for c in cols) + " |")
    q = res["review_queue"]
    out += ["", "**Review queue (the checks, without the answers):**",
            f"- {q['wrong_and_flagged']} of {q['wrong_documents']} documents with a wrong key field were flagged for review.",
            f"- {q['flagged']} documents were flagged. {q['flagged_key_fields_right']} of them had every key field right "
            f"but a wrong line item; {q['false_alarms']} were false alarms (everything right, line items included).",
            f"- Wrong key field but passed every check: {', '.join(q['wrong_but_passed']) or 'none'}.",
            (f"- Wrong line item but passed every check: {', '.join(q['item_errors_passed']) or 'none'}."
             if q["item_errors_passed"] is not None else "- Line items: not read by this extractor."),
            f"- Average time per document: {res['seconds_per_document']} s."]
    return "\n".join(out) + "\n"


def compare_md(runs: list[tuple[str, str, str]]) -> str:
    """One table across runs. runs = [(method label, layouts label, run folder with metrics.json), ...]"""
    out = ["| Method | Layouts | Documents | All key fields right | Line items read | Wrong documents caught "
           "by the checks | False alarms | Seconds per document |",
           "|---|---|---|---|---|---|---|---|"]
    for method, layouts, folder in runs:
        r = json.loads(Path(folder, "metrics.json").read_text(encoding="utf-8"))
        g, q = r["groups"]["all"], r["review_queue"]
        items = f"{g['item_recall']}%" if g["item_recall"] else "none"
        caught = f"{q['wrong_and_flagged']} of {q['wrong_documents']}" if q["wrong_documents"] else "nothing was wrong"
        out.append(f"| {method} | {layouts} | {r['documents']} | **{g['fully_correct']}%** | {items} | {caught} | "
                   f"{q['false_alarms']} | {r['seconds_per_document']} |")
    return "\n".join(out) + "\n"


def write(res: dict, out_dir: str, title: str) -> None:
    Path(out_dir, "REPORT.md").write_text(report_md(res, title), encoding="utf-8")
    Path(out_dir, "metrics.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
