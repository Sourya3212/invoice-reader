"""Checks that catch wrong readings before anyone posts them to the books.

A document with any issue goes to the review queue instead of straight into the export. The checks use the
document's own arithmetic, so they work without knowing the right answer.
"""
from __future__ import annotations

import datetime as dt
import re

from .normalize import KNOWN_CURRENCIES, currency_from_text, parse_date
from .schema import Invoice

TOL = 0.02  # two cents of rounding slack
NUMERIC_DATE = re.compile(r"\b\d{1,2}([./])\d{1,2}\1\d{4}\b")


def _iso(s) -> bool:
    try:
        dt.date.fromisoformat(s)
        return True
    except (TypeError, ValueError):
        return False


def _swapped_dates(inv: Invoice, text: str) -> list[str]:
    """A printed date like 07/08/2026 can be read two ways. The document's own convention decides (US dollars: month
    first; otherwise day first, as parse_date does), so an answer that matches only the other reading has its day and
    month swapped. The arithmetic checks can't see this: a model once read a US receipt's 07/08/2026 as 7 August."""
    currency = currency_from_text(text) or inv.currency
    meant = {}  # each printed numeric date, as the document means it -> as printed
    for m in NUMERIC_DATE.finditer(text):
        iso = parse_date(m.group(0), currency)
        if iso:
            meant[iso] = m.group(0)
    issues = []
    for label, value in (("issue date", inv.issue_date), ("due date", inv.due_date)):
        if not _iso(value) or value in meant:
            continue
        d = dt.date.fromisoformat(value)
        try:
            other = dt.date(d.year, d.day, d.month).isoformat()  # the same day and month the other way round
        except ValueError:
            continue
        if other in meant:
            issues.append(f"{label} {value} looks like {meant[other]} read the wrong way round (day and month swapped?)")
    return issues


def check(inv: Invoice, text: str | None = None) -> list[str]:
    """Every problem found in one answer. With the document's text, printed dates are checked too."""
    issues = []
    if not inv.vendor_name.strip():
        issues.append("vendor name missing")
    if not _iso(inv.issue_date):
        issues.append("issue date missing or not a date")
    if inv.due_date and not _iso(inv.due_date):
        issues.append("due date is not a date")
    if _iso(inv.issue_date) and inv.due_date and _iso(inv.due_date) and inv.due_date < inv.issue_date:
        issues.append("due date is before the issue date (day and month swapped?)")
    if text:
        issues += _swapped_dates(inv, text)
    if inv.currency not in KNOWN_CURRENCIES:
        issues.append(f"unknown currency {inv.currency!r}")
    if inv.total <= 0:
        issues.append("total missing")
    if abs(inv.subtotal - inv.discount + inv.shipping + inv.tax - inv.total) > TOL:
        issues.append(f"subtotal - discount + shipping + tax = "
                      f"{inv.subtotal - inv.discount + inv.shipping + inv.tax:.2f}, but total is {inv.total:.2f}")
    if inv.line_items:
        s = sum(it.amount for it in inv.line_items)
        if abs(s - inv.subtotal) > TOL:
            issues.append(f"line items add up to {s:.2f}, but subtotal is {inv.subtotal:.2f}")
        for it in inv.line_items:
            if abs(it.quantity * it.unit_price - it.amount) > max(TOL, 0.006 * abs(it.amount)):
                issues.append(f"line '{it.description[:30]}': {it.quantity:g} x {it.unit_price:.2f} != {it.amount:.2f}")
    return issues
