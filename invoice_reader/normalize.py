"""Turn printed money, dates and currency symbols into clean values.

Real invoices write the same number many ways: $1,234.56, 1.234,56 €, Rs. 1,23,456.00. These helpers are
shared by the rule-based extractor and by the checks that clean up the AI model's answers.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Optional

MONEY_RE = re.compile(r"(?:A\$|\$|£|€|Rs\.?\s?)?\s?-?\d[\d.,]*\d(?:\s?€)?|\d")

CURRENCY_SIGNS = [("A$", "AUD"), ("Rs.", "NPR"), ("Rs ", "NPR"), ("€", "EUR"), ("£", "GBP"), ("$", "USD")]
KNOWN_CURRENCIES = {"USD", "GBP", "EUR", "AUD", "NPR"}


def parse_money(s: str) -> Optional[float]:
    """'$1,234.56' -> 1234.56; '1.234,56 €' -> 1234.56; 'Rs. 1,23,456.00' -> 123456.0; '-£5.00' -> -5.0."""
    if s is None:
        return None
    t = s.strip().replace("−", "-")
    # Drop currency marks first: the dot in "Rs." must not be read as a decimal point.
    t = re.sub(r"(?i)\brs\.?|a\$|\b(?:usd|gbp|eur|aud|npr)\b|[$£€]", "", t).strip()
    neg = t.startswith("-") or t.startswith("(")
    t = re.sub(r"[^\d.,]", "", t).strip(".,")
    if not t or not re.search(r"\d", t):
        return None
    if "," in t and "." in t:
        # whichever separator comes last is the decimal point
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif "," in t:
        # a single comma followed by exactly two digits at the end is a decimal comma (German style)
        t = t.replace(",", ".") if re.search(r",\d{2}$", t) and t.count(",") == 1 else t.replace(",", "")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def currency_from_text(text: str) -> Optional[str]:
    for sign, code in CURRENCY_SIGNS:
        if sign in text:
            return code
    m = re.search(r"\b(USD|GBP|EUR|AUD|NPR)\b", text)
    return m.group(1) if m else None


DATE_FORMATS_UNAMBIGUOUS = ["%Y-%m-%d", "%d.%m.%Y", "%d %b %Y", "%d %B %Y", "%B %d, %Y", "%b %d, %Y"]


def parse_date(s: str, currency: Optional[str] = None) -> Optional[str]:
    """Return an ISO date. dd/mm vs mm/dd is decided by the currency: US dollars mean month first."""
    if not s:
        return None
    t = re.sub(r"\s+", " ", s.strip().strip(".,"))
    for f in DATE_FORMATS_UNAMBIGUOUS:
        try:
            return dt.datetime.strptime(t, f).date().isoformat()
        except ValueError:
            pass
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
    if m:
        a, b, y = map(int, m.groups())
        order = [(a, b), (b, a)] if currency == "USD" else [(b, a), (a, b)]  # (month, day)
        for month, day in order:
            try:
                return dt.date(y, month, day).isoformat()
            except ValueError:
                continue
    return None


def money_tokens(line: str) -> list[float]:
    """Every money-looking number on a line, in order (percentages are skipped)."""
    out = []
    # (?!\d) stops a match ending mid-number, so "8.875%" can't yield "8.87"; the other lookahead skips percentages.
    for m in re.finditer(r"(?:A\$|\$|£|€|Rs\.?\s?)?\s?-?\d[\d.,]*\d(?:\s?€)?(?![\d.,]*\s?%)(?!\d)", line):
        tok = m.group(0)
        if re.search(r"\d[.,]\d{2}(?:\s?€)?$", tok):  # money has two decimals
            v = parse_money(tok)
            if v is not None:
                out.append(v)
    return out
