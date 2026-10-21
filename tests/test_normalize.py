from invoice_reader.normalize import currency_from_text, money_tokens, parse_date, parse_money


def test_money_formats():
    assert parse_money("$1,234.56") == 1234.56
    assert parse_money("£12.00") == 12.0
    assert parse_money("A$1,000.10") == 1000.10
    assert parse_money("1.234,56 €") == 1234.56
    assert parse_money("12,50 €") == 12.5
    assert parse_money("Rs. 3,910.40") == 3910.40  # the dot in "Rs." is not a decimal point
    assert parse_money("Rs. 1,23,456.00") == 123456.0  # lakh grouping
    assert parse_money("-$5.00") == -5.0


def test_money_tokens_skip_percentages():
    assert money_tokens("VAT (20%) £24.00") == [24.0]
    assert money_tokens("Sales Tax (8.875%) $10.65") == [10.65]


def test_dates_follow_the_currency():
    assert parse_date("10/01/2026", "USD") == "2026-10-01"  # month first in US dollars
    assert parse_date("10/01/2026", "GBP") == "2026-01-10"  # day first elsewhere
    assert parse_date("04.09.2026") == "2026-09-04"
    assert parse_date("4 Sep 2026") == "2026-09-04"
    assert parse_date("2026-09-04") == "2026-09-04"


def test_currency_signs():
    assert currency_from_text("Total A$12.00") == "AUD"
    assert currency_from_text("Rs. 500.00") == "NPR"
    assert currency_from_text("12,00 €") == "EUR"
