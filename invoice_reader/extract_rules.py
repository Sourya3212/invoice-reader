"""Baseline extractor: hand-written rules (labels + regular expressions), no AI.

It reads the header fields only and leaves line items empty. It exists to be beaten: the evaluation reports it
next to the AI extractor, so the gain from the model is measured, not assumed.
"""
from __future__ import annotations

import re
from typing import Optional

from .normalize import currency_from_text, money_tokens, parse_date, parse_money
from .schema import Invoice

DATE_TOKEN = r"(\d{4}-\d{2}-\d{2}|\d{1,2}[./]\d{1,2}[./]\d{4}|\d{1,2} [A-Z][a-z]{2,8} \d{4}|[A-Z][a-z]{2,8} \d{1,2}, \d{4})"
SKIP_FIRST = re.compile(r"(?i)^(invoice|tax invoice|from|statement)\b")


def _after(text: str, label_re: str, window: int = 70, last: bool = False) -> Optional[str]:
    hits = list(re.finditer(label_re, text))
    if not hits:
        return None
    m = hits[-1] if last else hits[0]
    return text[m.end(): m.end() + window]


def _money_after(text: str, label_re: str) -> Optional[float]:
    # Totals sit at the bottom of the page, so the LAST matching label wins: "Line total" in a column header
    # or "Tax" in an item name must not be read as the grand total or the tax line.
    w = _after(text, label_re, last=True)
    if w is None:
        return None
    toks = money_tokens(w)
    return toks[0] if toks else None


def _date_after(text: str, label_re: str, currency: Optional[str]) -> Optional[str]:
    w = _after(text, label_re, window=40)
    m = re.search(DATE_TOKEN, w or "")
    return parse_date(m.group(1), currency) if m else None


def extract(text: str) -> Invoice:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    vendor = next((ln for ln in lines if not SKIP_FIRST.match(ln)), "")
    vendor = vendor.split(",")[0].strip()
    # OCR reads across the page, so the vendor and "Invoice No: ..." can share one line: cut at the first label.
    vendor = re.split(r"(?i)\s+(?:invoice no|inv #|invoice date|date issued|reference)\b", vendor)[0].strip()
    currency = currency_from_text(text) or "USD"
    m = re.search(r"(?i)(?:invoice no|inv #|reference|receipt no\.?)\s*[:#.]?\s*([A-Z0-9][A-Z0-9/\-]*\d)", text)
    number = m.group(1) if m else None
    issue = _date_after(text, r"(?i)(?<!due )\b(?:invoice date|date issued|issued|date)\b\s*:?\s*", currency)
    due = _date_after(text, r"(?i)\b(?:due date|payment due|please pay by)\b\s*:?\s*", currency)
    subtotal = _money_after(text, r"(?i)\bsubtotal\b")
    tax = _money_after(text, r"(?i)\b(?:vat|gst|sales tax|mwst\.?)\b")
    discount = _money_after(text, r"(?i)\bdiscount\b")
    shipping = _money_after(text, r"(?i)\bshipping\b")
    total = _money_after(text, r"(?i)(?<!sub)\b(?:total due|amount due|balance due|total)\b")
    return Invoice(vendor_name=vendor, invoice_number=number, issue_date=issue or "", due_date=due,
                   currency=currency, subtotal=subtotal or 0.0, discount=abs(discount or 0.0),
                   shipping=shipping or 0.0, tax=tax or 0.0, total=total or 0.0, line_items=[])
