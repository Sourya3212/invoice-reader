# New layouts: local AI (qwen3.5:9b on Ollama)

30 documents. Accuracy in % (money to the cent, dates exact).

| Field | all (n=30) | digital (n=22) | scan (n=8) |
|---|---|---|---|
| vendor_name | 100.0 | 100.0 | 100.0 |
| invoice_number | 100.0 | 100.0 | 100.0 |
| issue_date | 100.0 | 100.0 | 100.0 |
| due_date | 100.0 | 100.0 | 100.0 |
| currency | 100.0 | 100.0 | 100.0 |
| subtotal | 100.0 | 100.0 | 100.0 |
| tax | 100.0 | 100.0 | 100.0 |
| total | 100.0 | 100.0 | 100.0 |
| discount | 100.0 | 100.0 | 100.0 |
| shipping | 100.0 | 100.0 | 100.0 |
| **all key fields right** | **100.0** | **100.0** | **100.0** |
| line items found (recall) | 96.7 | 95.3 | 100.0 |
| line items right (precision) | 96.7 | 95.3 | 100.0 |

**Review queue (the checks, without the answers):**
- 0 of 0 documents with a wrong key field were flagged for review.
- 1 documents were flagged. 1 of them had every key field right but a wrong line item; 0 were false alarms (everything right, line items included).
- Wrong key field but passed every check: none.
- Wrong line item but passed every check: doc_017.
- Average time per document: 12.03 s.
