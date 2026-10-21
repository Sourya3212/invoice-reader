"""Generate a synthetic test set of invoices and receipts, with the correct answer for each one.

Everything here is made up: vendors, customers, items and amounts. No real client data is used.

    python data_gen/generate.py --count 50 --out data

Writes data/docs/<id>.pdf (digital, with a text layer) or <id>.jpg/.png (a "scan": rendered, rotated, blurred
and noised so OCR has to work for it), data/truth/<id>.json (the correct fields) and data/manifest.csv.
The same --seed always produces the same set.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import random
import sys
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from invoice_reader.schema import Invoice, LineItem  # noqa: E402

# ------------------------------------------------------------------ locales: how money, dates and tax look
LOCALES = {
    "US": {"currency": "USD", "date": "%m/%d/%Y", "tax_label": "Sales Tax", "rates": [0.0, 0.06, 0.0725, 0.08875],
           "cities": ["Austin, TX 78701", "Denver, CO 80202", "Columbus, OH 43215", "Portland, OR 97204"]},
    "UK": {"currency": "GBP", "date": "%d/%m/%Y", "tax_label": "VAT", "rates": [0.20],
           "cities": ["Leeds LS1 4AP", "Bristol BS1 5TR", "Manchester M2 3HQ", "Brighton BN1 1AE"]},
    "AU": {"currency": "AUD", "date": "%d %b %Y", "tax_label": "GST", "rates": [0.10],
           "cities": ["Melbourne VIC 3000", "Brisbane QLD 4000", "Perth WA 6000"]},
    "DE": {"currency": "EUR", "date": "%d.%m.%Y", "tax_label": "MwSt.", "rates": [0.19, 0.07],
           "cities": ["10115 Berlin", "80331 München", "20095 Hamburg"]},
    "NP": {"currency": "NPR", "date": "%Y-%m-%d", "tax_label": "VAT", "rates": [0.13],
           "cities": ["Kathmandu 44600", "Lalitpur 44700", "Pokhara 33700"]},
}

SECTORS = {
    "office": {"vendors": ["Brightline Office Supply", "Northgate Stationers", "Kestrel Paper Co."],
               "items": [("A4 copy paper, 5 reams", 18, 42), ("Gel pens, box of 12", 6, 15), ("Stapler, heavy duty", 12, 30),
                         ("Toner cartridge", 45, 120), ("Desk organiser", 9, 25), ("Whiteboard markers, 8 pack", 5, 14)],
               "goods": True},
    "software": {"vendors": ["Cloudnest Software Ltd", "Pixelgrid Studio", "Ledgerly Apps"],
                 "items": [("Annual licence, standard plan", 240, 960), ("Additional user seat", 60, 180),
                           ("Onboarding session", 150, 400), ("Priority support, 12 months", 300, 900)],
                 "goods": False},
    "services": {"vendors": ["Harbor and Finch Consulting", "Summit Bookkeeping Services", "Bluepine Cleaning Co."],
                 "items": [("Monthly bookkeeping", 350, 900), ("Payroll processing", 120, 300), ("Office deep clean", 180, 420),
                           ("Tax return preparation", 400, 1200), ("Advisory call", 90, 250)],
                 "goods": False},
    "printing": {"vendors": ["Quickprint Hub", "Inkwell Print House", "Paperplane Press"],
                 "items": [("Business cards, 500", 35, 90), ("Flyers A5, 1,000", 60, 160), ("Roll-up banner", 80, 190),
                           ("Brochures, 250", 120, 300)],
                 "goods": True},
}
RECEIPT_SHOPS = {
    "vendors": ["Corner Bean Cafe", "Himal Grocers", "Daily Fresh Mart", "The Lunch Box"],
    "items": [("Latte", 3, 6), ("Sandwich", 5, 11), ("Bottled water", 1, 3), ("Bananas, 1 kg", 2, 4),
              ("Rice, 5 kg", 8, 16), ("Muffin", 2, 5), ("Green tea", 2, 5)],
}
CUSTOMERS = ["Alder Accounting LLP", "Maple Street Dental", "Riverside Tutors", "Orbit Logistics", "Fernhill Bakery",
             "Crescent Legal", "Lumen Architects", "Tidewater Florists"]
STREETS = ["12 Market Street", "48 Station Road", "7 Harbour Lane", "220 Elm Avenue", "15 Mill Road", "3 Kings Parade"]


# ------------------------------------------------------------------ formatting
def money(x: float, loc: str) -> str:
    if loc == "DE":
        s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{s} €"
    if loc == "NP":
        whole, frac = f"{x:.2f}".split(".")
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        return "Rs. " + ",".join(groups + [tail]) + "." + frac if groups else f"Rs. {tail}.{frac}"
    sym = {"US": "$", "UK": "£", "AU": "A$"}[loc]
    return f"{sym}{x:,.2f}"


def qty(q: float) -> str:
    return f"{q:g}"


def r2(x: float) -> float:
    return round(x + 1e-9, 2)


# ------------------------------------------------------------------ one document's data
def make_invoice(rng: random.Random, i: int, template_set: str = "dev"):
    kind = "receipt" if rng.random() < 0.22 else "invoice"
    loc = rng.choice(list(LOCALES))
    held_tmpl = None
    if template_set == "heldout":  # layouts and labels the rule-based extractor was never written for
        held_tmpl = rng.choice(["bill", "german"]) if kind == "invoice" else "receipt2"
        if held_tmpl == "german":
            loc = "DE"
    L = LOCALES[loc]
    issue = dt.date(2026, 7, 1) + dt.timedelta(days=rng.randrange(0, 107))
    if kind == "receipt":
        vendor = rng.choice(RECEIPT_SHOPS["vendors"])
        catalog, goods, sector = RECEIPT_SHOPS["items"], True, "retail"
        number = rng.choice([f"R-{rng.randrange(100, 99999):05d}", f"{rng.randrange(1000, 9999)}-{rng.randrange(10, 99)}"])
        due = None
    else:
        sector = rng.choice(list(SECTORS))
        S = SECTORS[sector]
        vendor, catalog, goods = rng.choice(S["vendors"]), S["items"], S["goods"]
        number = rng.choice([f"INV-2026-{rng.randrange(1, 9999):04d}", f"A{rng.randrange(1000, 99999)}",
                             f"2026/{rng.randrange(1, 9999):04d}", f"SO-{rng.randrange(10000, 99999)}"])
        due = issue + dt.timedelta(days=rng.choice([7, 14, 30, 45]))
    n_items = rng.randint(1, 3) if kind == "receipt" else rng.randint(1, 6)
    items = []
    for desc, lo, hi in rng.sample(catalog, k=min(n_items, len(catalog))):
        if sector == "services" and rng.random() < 0.5:
            q, unit, desc = rng.choice([1.5, 2, 3.5, 4, 7.5, 10]), r2(rng.uniform(40, 120)), desc + " (hours)"
        else:
            q, unit = (rng.randint(1, 4) if kind == "receipt" else rng.randint(1, 10)), r2(rng.uniform(lo, hi))
        items.append(LineItem(description=desc, quantity=q, unit_price=unit, amount=r2(q * unit)))
    if loc == "NP":  # rupee amounts are larger
        items = [LineItem(description=it.description, quantity=it.quantity, unit_price=r2(it.unit_price * 130),
                          amount=r2(it.quantity * r2(it.unit_price * 130))) for it in items]
    subtotal = r2(sum(it.amount for it in items))
    discount = r2(subtotal * rng.choice([0.05, 0.10])) if kind == "invoice" and rng.random() < 0.25 else 0.0
    shipping = r2(rng.uniform(5, 25) * (130 if loc == "NP" else 1)) if goods and kind == "invoice" and rng.random() < 0.3 else 0.0
    rate = rng.choice(L["rates"])
    tax = r2((subtotal - discount) * rate)
    total = r2(subtotal - discount + shipping + tax)
    inv = Invoice(vendor_name=vendor, invoice_number=number, issue_date=issue.isoformat(),
                  due_date=due.isoformat() if due else None, currency=L["currency"], subtotal=subtotal,
                  discount=discount, shipping=shipping, tax=tax, total=total, line_items=items)
    meta = {"kind": kind, "locale": loc, "rate": rate, "sector": sector,
            "customer": rng.choice(CUSTOMERS), "street": rng.choice(STREETS), "city": rng.choice(L["cities"]),
            "cust_street": rng.choice(STREETS), "cust_city": rng.choice(L["cities"]),
            "template": held_tmpl or ("receipt" if kind == "receipt" else rng.choice(["classic", "modern", "statement"]))}
    return inv, meta


# ------------------------------------------------------------------ HTML templates (deliberately different labels)
CSS = """
body { font-family: sans-serif; font-size: 10pt; color: #222; }
h1 { font-size: 20pt; margin: 0 0 6pt 0; }
table { width: 100%; border-collapse: collapse; }
th { text-align: left; border-bottom: 1px solid #555; padding: 3pt; font-size: 9pt; }
td { padding: 3pt; border-bottom: 1px solid #ddd; font-size: 9.5pt; }
.r { text-align: right; }
.muted { color: #666; font-size: 8.5pt; }
.big { font-size: 13pt; font-weight: bold; }
"""


def d(date_iso: str | None, loc: str) -> str:
    return dt.date.fromisoformat(date_iso).strftime(LOCALES[loc]["date"]) if date_iso else ""


def totals_rows(inv: Invoice, meta, label_total: str) -> str:
    loc, L = meta["locale"], LOCALES[meta["locale"]]
    rows = [("Subtotal", inv.subtotal)]
    if inv.discount:
        rows.append(("Discount", -inv.discount))
    if inv.shipping:
        rows.append(("Shipping", inv.shipping))
    pct = f"{meta['rate'] * 100:g}%"
    rows.append((f"{L['tax_label']} ({pct})", inv.tax))
    out = "".join(f"<tr><td></td><td></td><td class='r'>{k}</td><td class='r'>{money(abs(v), loc) if v >= 0 else '-' + money(abs(v), loc)}</td></tr>"
                  for k, v in rows)
    return out + f"<tr><td></td><td></td><td class='r'><b>{label_total}</b></td><td class='r big'>{money(inv.total, loc)}</td></tr>"


def items_rows(inv: Invoice, loc: str, unit_label: bool = False) -> str:
    return "".join(f"<tr><td>{it.description}</td><td class='r'>{qty(it.quantity)}</td>"
                   f"<td class='r'>{money(it.unit_price, loc)}</td><td class='r'>{money(it.amount, loc)}</td></tr>"
                   for it in inv.line_items)


def html_classic(inv: Invoice, m) -> str:
    loc = m["locale"]
    return f"""
<h1>INVOICE</h1>
<table><tr><td style='border:none'><b>{inv.vendor_name}</b><br>{m['street']}<br>{m['city']}</td>
<td style='border:none' class='r'>Invoice No: <b>{inv.invoice_number}</b><br>Invoice Date: {d(inv.issue_date, loc)}<br>
Due Date: {d(inv.due_date, loc)}</td></tr></table>
<p><b>Bill To:</b><br>{m['customer']}<br>{m['cust_street']}<br>{m['cust_city']}</p>
<table><tr><th>Description</th><th class='r'>Qty</th><th class='r'>Unit Price</th><th class='r'>Amount</th></tr>
{items_rows(inv, loc)}{totals_rows(inv, m, 'Total Due')}</table>
<p class='muted'>Thank you for your business. Payment terms: due by {d(inv.due_date, loc)}.</p>"""


def html_modern(inv: Invoice, m) -> str:
    loc = m["locale"]
    title = "TAX INVOICE" if loc in ("AU", "NP") else "Invoice"
    return f"""
<p class='big'>{inv.vendor_name}</p><p class='muted'>{m['street']} · {m['city']}</p>
<h1>{title}</h1>
<p>Inv #: {inv.invoice_number} &nbsp;&nbsp; Date issued: {d(inv.issue_date, loc)} &nbsp;&nbsp; Payment due: {d(inv.due_date, loc)}</p>
<p>Customer: {m['customer']}</p>
<table><tr><th>Item</th><th class='r'>Quantity</th><th class='r'>Price</th><th class='r'>Line total</th></tr>
{items_rows(inv, loc)}{totals_rows(inv, m, 'Amount due')}</table>"""


def html_statement(inv: Invoice, m) -> str:
    loc = m["locale"]
    return f"""
<p class='muted'>From</p><p><b>{inv.vendor_name}</b>, {m['street']}, {m['city']}</p>
<h1>Statement and Invoice</h1>
<table>
<tr><td style='border:none'>Reference</td><td style='border:none'>{inv.invoice_number}</td></tr>
<tr><td style='border:none'>Issued</td><td style='border:none'>{d(inv.issue_date, loc)}</td></tr>
<tr><td style='border:none'>Please pay by</td><td style='border:none'>{d(inv.due_date, loc)}</td></tr>
<tr><td style='border:none'>Client</td><td style='border:none'>{m['customer']}</td></tr></table>
<p></p>
<table><tr><th>Work performed</th><th class='r'>Units</th><th class='r'>Rate</th><th class='r'>Charge</th></tr>
{items_rows(inv, loc)}{totals_rows(inv, m, 'Balance due')}</table>"""


def html_receipt(inv: Invoice, m) -> str:
    loc = m["locale"]
    lines = "".join(f"<tr><td>{qty(it.quantity)} x {it.description}</td><td class='r'>{money(it.amount, loc)}</td></tr>"
                    for it in inv.line_items)
    L = LOCALES[loc]
    return f"""
<p style='text-align:center'><b>{inv.vendor_name}</b><br>{m['street']}<br>{m['city']}</p>
<p>Date: {d(inv.issue_date, loc)} &nbsp; 14:{(int(inv.subtotal * 7) % 50) + 10:02d}<br>Receipt No. {inv.invoice_number}</p>
<table>{lines}
<tr><td class='r'>Subtotal</td><td class='r'>{money(inv.subtotal, loc)}</td></tr>
<tr><td class='r'>{L['tax_label']} {m['rate'] * 100:g}%</td><td class='r'>{money(inv.tax, loc)}</td></tr>
<tr><td class='r'><b>TOTAL</b></td><td class='r big'>{money(inv.total, loc)}</td></tr></table>
<p style='text-align:center' class='muted'>Paid by card. Thank you!</p>"""


# ------------------------------------------------------------------ held-out layouts (never used to write the rules)
def _held_totals(inv: Invoice, m, labels: dict) -> str:
    loc = m["locale"]
    rows = [(labels["sub"], money(inv.subtotal, loc))]
    if inv.discount:
        rows.append((labels["disc"], "-" + money(inv.discount, loc)))
    if inv.shipping:
        rows.append((labels["ship"], money(inv.shipping, loc)))
    rows.append((labels["tax"].format(pct=f"{m['rate'] * 100:g}%"), money(inv.tax, loc)))
    body = "".join(f"<tr><td></td><td></td><td class='r'>{k}</td><td class='r'>{v}</td></tr>" for k, v in rows)
    return body + (f"<tr><td></td><td></td><td class='r'><b>{labels['total']}</b></td>"
                   f"<td class='r big'>{money(inv.total, loc)}</td></tr>")


def html_bill(inv: Invoice, m) -> str:
    loc, L = m["locale"], LOCALES[m["locale"]]
    rows = "".join(f"<tr><td>{qty(it.quantity)}</td><td>{it.description}</td><td class='r'>{money(it.unit_price, loc)}</td>"
                   f"<td class='r'>{money(it.amount, loc)}</td></tr>" for it in inv.line_items)
    labels = {"sub": "Net amount", "disc": "Less discount", "ship": "Delivery",
              "tax": L["tax_label"] + " @ {pct}", "total": "Grand total"}
    return f"""
<p class='big'>{inv.vendor_name}</p><p class='muted'>{m['street']}, {m['city']}</p>
<h1>Bill</h1>
<table><tr><td style='border:none'>Bill No.</td><td style='border:none'>{inv.invoice_number}</td>
<td style='border:none'>Billing date</td><td style='border:none'>{d(inv.issue_date, loc)}</td></tr>
<tr><td style='border:none'>Billed to</td><td style='border:none'>{m['customer']}</td>
<td style='border:none'>Pay before</td><td style='border:none'>{d(inv.due_date, loc)}</td></tr></table>
<p></p>
<table><tr><th>Qty</th><th>Description</th><th class='r'>Each</th><th class='r'>Total</th></tr>
{rows}{_held_totals(inv, m, labels)}</table>"""


def html_german(inv: Invoice, m) -> str:
    loc = m["locale"]
    labels = {"sub": "Zwischensumme", "disc": "Rabatt", "ship": "Versand", "tax": "MwSt. {pct}",
              "total": "Gesamtbetrag"}
    return f"""
<p><b>{inv.vendor_name}</b> · {m['street']} · {m['city']}</p>
<h1>Rechnung</h1>
<p>Rechnungsnummer: {inv.invoice_number}<br>Rechnungsdatum: {d(inv.issue_date, loc)}<br>
Fällig am: {d(inv.due_date, loc)}</p>
<p>Kunde: {m['customer']}</p>
<table><tr><th>Beschreibung</th><th class='r'>Menge</th><th class='r'>Einzelpreis</th><th class='r'>Betrag</th></tr>
{items_rows(inv, loc)}{_held_totals(inv, m, labels)}</table>"""


def html_receipt2(inv: Invoice, m) -> str:
    loc = m["locale"]
    lines = "".join(f"<tr><td>{it.description} x{qty(it.quantity)}</td><td class='r'>{money(it.amount, loc)}</td></tr>"
                    for it in inv.line_items)
    return f"""
<p style='text-align:center'><b>{inv.vendor_name}</b><br>{m['city']}</p>
<p>Order #{inv.invoice_number}<br>{d(inv.issue_date, loc)}</p>
<table>{lines}
<tr><td class='r'>Sub-total</td><td class='r'>{money(inv.subtotal, loc)}</td></tr>
<tr><td class='r'>Tax</td><td class='r'>{money(inv.tax, loc)}</td></tr>
<tr><td class='r'><b>Amount paid</b></td><td class='r big'>{money(inv.total, loc)}</td></tr></table>"""


TEMPLATES = {"classic": html_classic, "modern": html_modern, "statement": html_statement, "receipt": html_receipt,
             "bill": html_bill, "german": html_german, "receipt2": html_receipt2}


# ------------------------------------------------------------------ render
def render_pdf(html: str, receipt: bool) -> pymupdf.Document:
    doc = pymupdf.open()
    w, h = (280, 520) if receipt else (595, 842)
    page = doc.new_page(width=w, height=h)
    page.insert_htmlbox(pymupdf.Rect(28, 28, w - 28, h - 28), html, css=CSS)
    return doc


def fake_scan(doc: pymupdf.Document, rng: random.Random) -> Image.Image:
    pix = doc[0].get_pixmap(dpi=rng.choice([150, 170, 200]), colorspace=pymupdf.csGRAY)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
    img = img.rotate(rng.uniform(-1.4, 1.4), expand=True, fillcolor=255, resample=Image.BICUBIC)
    img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 0.8)))
    arr = np.asarray(img).astype(np.int16)
    arr = arr + np.random.default_rng(rng.randrange(1 << 30)).normal(0, rng.uniform(4, 12), arr.shape).astype(np.int16)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=50)
    ap.add_argument("--out", default="data")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--scan-share", type=float, default=0.4)
    ap.add_argument("--templates", choices=["dev", "heldout"], default="dev",
                    help="dev: the layouts the rules were written against; heldout: new layouts and labels")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    out = Path(a.out)
    (out / "docs").mkdir(parents=True, exist_ok=True)
    (out / "truth").mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(1, a.count + 1):
        doc_id = f"doc_{i:03d}"
        inv, meta = make_invoice(rng, i, a.templates)
        html = TEMPLATES[meta["template"]](inv, meta)
        pdf = render_pdf(html, meta["template"] in ("receipt", "receipt2"))
        scanned = rng.random() < a.scan_share
        if scanned:
            ext = rng.choice(["jpg", "png"])
            img = fake_scan(pdf, rng)
            path = out / "docs" / f"{doc_id}.{ext}"
            img.save(path, quality=rng.randint(62, 85)) if ext == "jpg" else img.save(path)
        else:
            path = out / "docs" / f"{doc_id}.pdf"
            pdf.save(path)
        (out / "truth" / f"{doc_id}.json").write_text(inv.model_dump_json(indent=1), encoding="utf-8")
        rows.append({"doc_id": doc_id, "file": path.name, "template": meta["template"], "locale": meta["locale"],
                     "scanned": scanned, "items": len(inv.line_items)})
    with open(out / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} documents to {out}: "
          f"{sum(r['scanned'] for r in rows)} scans, {sum(not r['scanned'] for r in rows)} digital PDFs")


if __name__ == "__main__":
    main()
