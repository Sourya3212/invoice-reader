# invoice-reader

**Read invoices and receipts into checked, structured data, on your own computer.**

Bookkeepers still retype invoices. This tool reads each document (PDF or scan), pulls out the fields an accountant
needs, checks that the numbers add up, and sends only the doubtful documents to a person. The AI model runs
locally through [Ollama](https://ollama.com), so client documents never leave the machine.

## Results

80 synthetic test documents, scored field by field against the correct answers: money to the cent, dates exactly.

| Method | Layouts | Documents | All key fields right | Line items read | Wrong documents caught by the checks | False alarms | Seconds per document |
|---|---|---|---|---|---|---|---|
| Rules only | Known (50) | 50 | **94.0%** | none | 3 of 3 | 0 | 0.0 |
| Local AI (qwen3.5:9b), run 1 | Known (50) | 50 | **94.0%** | 94.9% | 3 of 3 | 0 | 11.6 |
| Local AI (qwen3.5:9b), run 2 | Known (50) | 50 | **94.0%** | 94.9% | 3 of 3 | 0 | 11.1 |
| Rules only | New (30) | 30 | **0.0%** | none | 30 of 30 | 0 | 0.0 |
| Local AI (qwen3.5:9b), run 1 | New (30) | 30 | **100.0%** | 96.7% | nothing was wrong | 0 | 12.0 |
| Local AI (qwen3.5:9b), run 2 | New (30) | 30 | **100.0%** | 96.7% | nothing was wrong | 0 | 10.5 |

"Key fields" are the vendor, invoice number, issue and due dates, currency, subtotal, tax and total. The local model
ran on one RTX 4060 laptop GPU (8 GB). Run 2 is a second full run, from a clean copy of this repository. Full
reports: `results/*/REPORT.md` and `results_heldout/*/REPORT.md`.

**What this shows:**
1. **Rules match the AI on layouts they were written for.** Both get 94%, and rules are instant. You don't need AI to read a known layout.
2. **Rules fail on layouts they haven't seen.** On the 30 new layouts they got 0% right, so every document would go to a person. The local AI got all 30 right, in both runs.
3. **Only the AI reads line items:** 95-97% of them.
4. **The checks caught every wrong key field.** In every run they flagged each document with a wrong key field, without knowing the answers, and raised no false alarms. One check was added on the way: in run 2, a US date read the wrong way round slipped through until the date check existed (see "How it was built").

**Known limits:**
- **Run to run:** the model runs at temperature 0 but isn't perfectly repeatable. Between the two runs, 3 of 80 answers changed, while accuracy stayed the same. The checks are what make that safe.
- **OCR on noisy scans:** a bold "1" was read as "4" in two totals. The checks caught both.
- **Pack sizes in item names:** in "Business cards, 500", the model sometimes took the 500 as the quantity. The checks caught these because the line no longer added up.
- **One case no check could see:** "Rice, 5 kg x2" was read as 10 x 344.76 instead of 2 x 1,723.80. Both make 3,447.60.

**Next steps:**
- Compare the printed quantity ("x2", or the Qty column) with the quantity read.
- Check vendors against the firm's vendor list.
- Test on real invoices, anonymised and with permission.

## How it works

```
document (PDF or scan)
   │
   ├─ read:     the PDF's own text layer, or Tesseract OCR for scans          invoice_reader/ingest.py
   ├─ extract:  rules (regular expressions)  OR  a local AI model             extract_rules.py / extract_llm.py
   │            the model must answer in a fixed JSON schema (every field
   │            required), and an invalid answer gets one retry
   ├─ check:    line items add up to the subtotal; subtotal - discount        validate.py
   │            + shipping + tax = total; each line is quantity x price;
   │            the due date is not before the issue date; each date is
   │            read the way the document writes dates (US: month first)
   └─ export:   invoices.xlsx with a "Ready" sheet and a "Needs review"       pipeline.py
                sheet, plus every line item
```

The checks use only the document itself (its arithmetic and the way it writes dates), so they work without knowing
the right answer. When OCR reads
"7.5 hours" as "75", the model copies the printed 75 and the check flags the line (75 x 60.69 is not 455.18). The
tool never "fixes" a printed number on its own.

## The test sets (synthetic, no real client data)

`data_gen/generate.py` builds invoices and receipts from made-up vendors, customers and items. It saves the correct
answer for every document, so accuracy is measured, not guessed. The same seed always gives the same documents and
answers: scans and answer files match byte for byte, and PDFs match in their text (only their embedded timestamps
differ).

- **Development set (50 documents).** Four layouts (classic, modern, statement and receipt) across five
  countries' money and date formats:
  - US dollars, month/day dates;
  - UK pounds;
  - Australian dollars;
  - euros with a decimal comma (1.234,56 €);
  - Nepali rupees with lakh grouping (Rs. 1,23,456.00).

  About 40% are fake scans: rendered, tilted, blurred and noised.
- **Held-out set (30 documents).** Three layouts the rules were never written for. One is a "Bill" with "Net amount"
  and "Grand total". One is a German "Rechnung" (Zwischensumme, MwSt., Gesamtbetrag). One is a new receipt style.
  This is the honest test of whether a method works on documents it has not seen.

## Run it

```bash
pip install -r requirements.txt          # plus Tesseract OCR, and Ollama with a model
python data_gen/generate.py --count 50 --out data
python data_gen/generate.py --count 30 --seed 7 --templates heldout --out data_heldout

python -m invoice_reader run  --docs data/docs --backend rules  --out results/rules
python -m invoice_reader eval --pred results/rules --truth data/truth --manifest data/manifest.csv
python -m invoice_reader run  --docs data_heldout/docs --backend rules --out results_heldout/rules
python -m invoice_reader eval --pred results_heldout/rules --truth data_heldout/truth --manifest data_heldout/manifest.csv

ollama serve                              # in a second terminal, only when you need it (Ctrl+C stops it)
ollama pull qwen3.5:9b                    # once: download the model
python -m invoice_reader run  --docs data/docs --backend ollama --out results/ollama-qwen3.5-9b
python -m invoice_reader eval --pred results/ollama-qwen3.5-9b --truth data/truth --manifest data/manifest.csv
python -m invoice_reader run  --docs data_heldout/docs --backend ollama --out results_heldout/ollama-qwen3.5-9b
python -m invoice_reader eval --pred results_heldout/ollama-qwen3.5-9b --truth data_heldout/truth --manifest data_heldout/manifest.csv

python tests/run.py                       # unit tests (also run under pytest)
```

Add `--limit 3` to `run` for a quick look at three documents, or `--resume` to finish a run that was stopped: it
keeps the answers already read, reruns the checks on them, and retries any document that failed.

## How it was built

I designed it and built it with Claude Code. Bugs found on the way, and what caught them:
- **The unit tests:** the dot in "Rs." was read as a decimal point, and "8.875%" was read as an amount of 8.87.
- **A practice run:** a PDF with its own text was being read by OCR, and the text came from the other test set.
  Both sets have a doc_002, and the text cache was keyed by file name. It's now keyed by the file's content and the
  reading code, so two different files never share cached text, and old cached text never hides a fix to the reader.
- **A close look at one answer:** PDFs often store "ffi" as one ligature character, so a vendor came out as
  "Brightline Oﬃce Supply". It looks right, but a spreadsheet search for "Office" misses it. The scorer had compared
  text with Python's `casefold()`, which quietly turns "ﬃ" into "ffi", so it counted the answer as right. The reader
  now spells ligatures out, and the scorer compares text the way a spreadsheet search does.
- **A second full run, from a clean copy:** 3 of 80 answers changed. One was a US receipt's "07/08/2026" read as
  7 August instead of 8 July. It passed every check, because nothing in the arithmetic was wrong. A new check now
  compares each date with how the document prints it. Rerun on the saved answers of both runs, without calling the
  model again, it caught that date, flagged none of the 80 correct answers, and raised no false alarms.

The rules baseline was tuned on the development set only, so its held-out score shows how rules behave on new
layouts.
