# Known layouts: local AI (qwen3.5:9b on Ollama)

50 documents. Accuracy in % (money to the cent, dates exact).

| Field | all (n=50) | digital (n=33) | scan (n=17) |
|---|---|---|---|
| vendor_name | 100.0 | 100.0 | 100.0 |
| invoice_number | 100.0 | 100.0 | 100.0 |
| issue_date | 100.0 | 100.0 | 100.0 |
| due_date | 98.0 | 97.0 | 100.0 |
| currency | 100.0 | 100.0 | 100.0 |
| subtotal | 100.0 | 100.0 | 100.0 |
| tax | 100.0 | 100.0 | 100.0 |
| total | 96.0 | 100.0 | 88.2 |
| discount | 100.0 | 100.0 | 100.0 |
| shipping | 100.0 | 100.0 | 100.0 |
| **all key fields right** | **94.0** | **97.0** | **88.2** |
| line items found (recall) | 94.9 | 99.1 | 86.0 |
| line items right (precision) | 94.9 | 99.1 | 86.0 |

**Review queue (the checks, without the answers):**
- 3 of 3 documents with a wrong key field were flagged for review.
- 8 documents were flagged. 5 of them had every key field right but a wrong line item; 0 were false alarms (everything right, line items included).
- Wrong key field but passed every check: none.
- Wrong line item but passed every check: none.
- Average time per document: 11.64 s.
