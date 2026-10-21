"""Get the text out of a document: the PDF's own text layer when it has one, OCR (Tesseract) when it does not."""
from __future__ import annotations

import io
import shutil
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image, ImageFilter, ImageOps

_WIN_TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if not shutil.which("tesseract") and _WIN_TESSERACT.exists():
    pytesseract.pytesseract.tesseract_cmd = str(_WIN_TESSERACT)


# PDFs often store "ffi", "fi" or "fl" as one ligature character. It looks the same on screen, but "Oﬃce" doesn't
# match "Office" in a spreadsheet search or a vendor lookup, so the letters are spelled out.
_LIGATURES = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
                            "ﬅ": "st", "ﬆ": "st"})


def plain_letters(text: str) -> str:
    return text.translate(_LIGATURES)


def _ocr(img: Image.Image) -> str:
    # Light clean-up helps Tesseract on noisy scans: greyscale, a little sharpening, auto-contrast.
    g = ImageOps.autocontrast(img.convert("L").filter(ImageFilter.MedianFilter(3)))
    return pytesseract.image_to_string(g, config="--psm 6")


def read_text(path: str | Path) -> tuple[str, str]:
    """Return (text, method), where method is 'pdf-text' or 'ocr'."""
    text, method = _read(Path(path))
    return plain_letters(text), method


def _read(path: Path) -> tuple[str, str]:
    if path.suffix.lower() == ".pdf":
        doc = pymupdf.open(path)
        text = "\n".join(page.get_text("text") for page in doc)
        if len(text.strip()) >= 30:
            return text, "pdf-text"
        pages = [Image.open(io.BytesIO(p.get_pixmap(dpi=300).tobytes("png"))) for p in doc]
        return "\n".join(_ocr(p) for p in pages), "ocr"
    return _ocr(Image.open(path)), "ocr"
