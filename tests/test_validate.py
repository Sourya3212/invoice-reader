from invoice_reader.schema import Invoice, LineItem
from invoice_reader.validate import check


def make(**kw):
    base = dict(vendor_name="Kestrel Paper Co.", invoice_number="INV-1", issue_date="2026-09-01",
                due_date="2026-09-15", currency="GBP", subtotal=100.0, tax=20.0, total=120.0,
                line_items=[LineItem(description="Paper", quantity=2, unit_price=50.0, amount=100.0)])
    base.update(kw)
    return Invoice(**base)


def test_clean_invoice_passes():
    assert check(make()) == []


def test_total_that_does_not_add_up_is_flagged():
    assert any("total is" in i for i in check(make(total=130.0)))


def test_line_items_must_match_subtotal():
    assert any("line items add up" in i for i in check(make(subtotal=90.0, total=110.0)))


def test_swapped_day_and_month_is_caught_by_due_before_issue():
    assert any("before the issue date" in i for i in check(make(due_date="2026-01-09")))


def test_ocr_lost_decimal_point_is_caught():
    # OCR read 7.5 hours as 75: 75 x 60.69 is not the printed 455.18
    bad = make(subtotal=455.18, tax=0.0, total=455.18,
               line_items=[LineItem(description="Payroll", quantity=75, unit_price=60.69, amount=455.18)])
    assert any("!=" in i for i in check(bad))


def test_us_date_read_day_first_is_flagged():
    # A US receipt prints 07/08/2026, which means 8 July. Read as 7 August, it passes every arithmetic check.
    text = "Corner Deli\nDate: 07/08/2026 14:19\nTotal $120.00"
    wrong = check(make(currency="USD", issue_date="2026-08-07", due_date=None), text)
    assert any("wrong way round" in i for i in wrong)
    assert check(make(currency="USD", issue_date="2026-07-08", due_date=None), text) == []


def test_uk_date_read_month_first_is_flagged():
    text = "Invoice Date: 06/08/2026\nDue Date: 20/08/2026\nTotal £120.00"
    assert any("wrong way round" in i for i in check(make(issue_date="2026-06-08", due_date="2026-08-20"), text))
    assert check(make(issue_date="2026-08-06", due_date="2026-08-20"), text) == []
