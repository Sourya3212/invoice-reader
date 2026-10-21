"""AI extractor: a language model reads the document text and returns the fields as JSON.

Default backend: a local model through Ollama (http://localhost:11434), so documents never leave the computer.
The model is forced into the Invoice JSON schema (Ollama structured outputs), the answer is validated with
pydantic, and an invalid answer gets one retry with the error shown to the model.
"""
from __future__ import annotations

import json
import os

import requests
from pydantic import ValidationError

from .schema import Invoice

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("INVOICE_MODEL", "qwen3.5:9b")

SYSTEM = """You read invoices and receipts for a bookkeeping firm. Return ONLY JSON that matches the schema.
Rules:
- Copy values exactly as printed; never invent a value. A field that is not on the document: null for text, 0 for money.
- Dates: ISO format YYYY-MM-DD. A date written 10/01/2026 on a document in US dollars is month/day/year; in any other
  currency it is day/month/year.
- currency: the ISO code (USD, GBP, EUR, AUD, NPR). "Rs." is NPR, "A$" is AUD.
- Money: plain numbers with a dot for decimals and no thousands separators (1.234,56 € becomes 1234.56).
  discount is a positive number even when printed with a minus sign.
- invoice_number: the invoice, reference or receipt number exactly as printed.
- vendor_name: the business that issued the document, not the customer.
- line_items: one entry per printed line, with quantity, unit_price and amount as printed. A receipt line like
  "4 x Latte  Rs. 2,620.80" has quantity 4, amount 2620.80 and unit_price 655.20."""


SYSTEM += """
- Labels vary. Tax may be labelled VAT, GST, Sales Tax or MwSt. The invoice number may be labelled Invoice No,
  Inv #, Reference or Receipt No. The due date may be labelled Due Date, Payment due or Please pay by."""


class ExtractionError(RuntimeError):
    pass


def _strict_schema() -> dict:
    """The Invoice JSON schema with EVERY field required. Fields with defaults are optional in pydantic's schema,
    and the model then simply leaves them out (tax came back 0, due dates came back empty). Required fields make it
    answer each one; null stays allowed where the field is optional."""
    s = Invoice.model_json_schema()
    s["required"] = list(s["properties"])
    for d in s.get("$defs", {}).values():
        d["required"] = list(d["properties"])
    return s


STRICT_SCHEMA = _strict_schema()


def _chat(messages: list[dict], model: str) -> str:
    r = requests.post(f"{OLLAMA_URL}/api/chat", timeout=600, json={
        "model": model, "messages": messages, "stream": False,
        "format": STRICT_SCHEMA, "options": {"temperature": 0},
        "think": False})
    r.raise_for_status()
    return r.json()["message"]["content"]


def extract(text: str, model: str = DEFAULT_MODEL) -> Invoice:
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Document text:\n\n{text}"}]
    last_error = None
    for _attempt in range(2):
        raw = _chat(messages, model)
        try:
            return Invoice.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = e
            messages += [{"role": "assistant", "content": raw},
                         {"role": "user", "content": f"That JSON was invalid: {e}. Return corrected JSON only."}]
    raise ExtractionError(f"model returned invalid JSON twice: {last_error}")
