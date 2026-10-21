# Known layouts: rules only (no AI)

50 documents. Accuracy in % (money to the cent, dates exact).

| Field | all (n=50) | digital (n=33) | scan (n=17) |
|---|---|---|---|
| vendor_name | 100.0 | 100.0 | 100.0 |
| invoice_number | 100.0 | 100.0 | 100.0 |
| issue_date | 100.0 | 100.0 | 100.0 |
| due_date | 100.0 | 100.0 | 100.0 |
| currency | 100.0 | 100.0 | 100.0 |
| subtotal | 100.0 | 100.0 | 100.0 |
| tax | 98.0 | 100.0 | 94.1 |
| total | 96.0 | 100.0 | 88.2 |
| discount | 100.0 | 100.0 | 100.0 |
| shipping | 100.0 | 100.0 | 100.0 |
| **all key fields right** | **94.0** | **100.0** | **82.4** |
| line items found (recall) | 0.0 | 0.0 | 0.0 |
| line items right (precision) | None | None | None |

**Review queue (the checks, without the answers):**
- 3 of 3 documents with a wrong key field were flagged for review.
- 3 documents were flagged. 0 of them had every key field right but a wrong line item; 0 were false alarms (everything right, line items included).
- Wrong key field but passed every check: none.
- Line items: not read by this extractor.
- Average time per document: 0.0 s.
