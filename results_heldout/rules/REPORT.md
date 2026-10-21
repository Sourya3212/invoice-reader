# New layouts: rules only (no AI)

30 documents. Accuracy in % (money to the cent, dates exact).

| Field | all (n=30) | digital (n=22) | scan (n=8) |
|---|---|---|---|
| vendor_name | 60.0 | 59.1 | 62.5 |
| invoice_number | 0.0 | 0.0 | 0.0 |
| issue_date | 36.7 | 40.9 | 25.0 |
| due_date | 23.3 | 18.2 | 37.5 |
| currency | 100.0 | 100.0 | 100.0 |
| subtotal | 0.0 | 0.0 | 0.0 |
| tax | 76.7 | 81.8 | 62.5 |
| total | 36.7 | 40.9 | 25.0 |
| discount | 86.7 | 86.4 | 87.5 |
| shipping | 80.0 | 77.3 | 87.5 |
| **all key fields right** | **0.0** | **0.0** | **0.0** |
| line items found (recall) | 0.0 | 0.0 | 0.0 |
| line items right (precision) | None | None | None |

**Review queue (the checks, without the answers):**
- 30 of 30 documents with a wrong key field were flagged for review.
- 30 documents were flagged. 0 of them had every key field right but a wrong line item; 0 were false alarms (everything right, line items included).
- Wrong key field but passed every check: none.
- Line items: not read by this extractor.
- Average time per document: 0.0 s.
