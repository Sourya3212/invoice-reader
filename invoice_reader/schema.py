"""The fields every invoice or receipt is read into.

The same model is used three ways: the test-set generator writes the correct answers in this shape,
the extractors must return it, and the evaluator compares the two field by field.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str
    quantity: float = 1
    unit_price: float
    amount: float


class Invoice(BaseModel):
    vendor_name: str
    invoice_number: Optional[str] = None  # receipts carry a receipt number here
    issue_date: str  # ISO 8601, YYYY-MM-DD
    due_date: Optional[str] = None  # ISO 8601; receipts have none
    currency: str  # ISO 4217 code: USD, GBP, EUR, AUD, NPR
    subtotal: float
    discount: float = 0
    shipping: float = 0
    tax: float = 0
    total: float
    line_items: list[LineItem] = Field(default_factory=list)


# The fields a bookkeeper must get right before a document can be posted.
KEY_FIELDS = ["vendor_name", "invoice_number", "issue_date", "due_date", "currency", "subtotal", "tax", "total"]
