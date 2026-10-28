"""FREE / OFFLINE extractor.
Step 1: OCR (RapidOCR) turns the bill image/PDF into text lines.
Step 2: a local LLM served by Ollama turns that text into structured JSON (schema.py).
No API key, no cost, nothing leaves your computer.
"""
import io
import json
import os
from io import StringIO

import numpy as np
import pandas as pd
import requests
from PIL import Image
from pydantic import ValidationError

from schema import CATEGORIES, Bill

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

SYSTEM = f"""You convert OCR text from a grocery bill into JSON.
Rules:
- Copy numbers exactly as printed. Never invent values; use null if not on the bill.
- One entry in "items" per purchased product (not totals, tax lines, payment lines or loyalty points).
- A decimal comma (3,49) means 3.49. Return plain numbers.
- Date format YYYY-MM-DD.
- Give each item a category from: {', '.join(CATEGORIES)}.
- If a discount line follows a product, subtract it into that product's total_price or put the bill-level amount in "discount" (positive number).
Return only JSON."""

_ocr_engine = None


# ----------------------------------------------------------------- OCR
def group_lines(detections) -> str:
    """Join OCR boxes that sit on the same visual row so 'MILK 1L   1.29' stays on one line."""
    rows = []
    for box, text in detections:
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        rows.append({"y": sum(ys) / len(ys), "h": max(ys) - min(ys), "x": min(xs), "t": text})
    rows.sort(key=lambda r: r["y"])

    lines, cur = [], []
    for r in rows:
        mean_y = sum(c["y"] for c in cur) / len(cur) if cur else None
        if cur and abs(r["y"] - mean_y) <= 0.6 * max(r["h"], 1):
            cur.append(r)
        else:
            if cur:
                lines.append(cur)
            cur = [r]
    if cur:
        lines.append(cur)
    return "\n".join("  ".join(c["t"] for c in sorted(line, key=lambda c: c["x"])) for line in lines)


def ocr_image(image_bytes: bytes) -> str:
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
    img = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
    result, _ = _ocr_engine(img)
    if not result:
        return ""
    return group_lines([(box, text) for box, text, _score in result])


def read_document(file_bytes: bytes, filename: str) -> str:
    if not filename.lower().endswith(".pdf"):
        return ocr_image(file_bytes)
    import fitz  # PyMuPDF
    pages = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page in doc:
            text = page.get_text().strip()
            if len(text) < 30:  # scanned page: render and OCR it
                text = ocr_image(page.get_pixmap(dpi=200).tobytes("png"))
            pages.append(text)
    return "\n".join(pages)


# ----------------------------------------------------------------- LLM
def _chat(messages, fmt=None, max_tokens=3000) -> str:
    body = {"model": MODEL, "messages": messages, "stream": False,
            "options": {"temperature": 0, "num_predict": max_tokens, "num_ctx": 8192}}
    if fmt is not None:
        body["format"] = fmt
    try:
        r = requests.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=600)
    except requests.ConnectionError:
        raise RuntimeError("Can't reach Ollama. Install it from ollama.com and make sure it is running.")
    if r.status_code == 404:
        raise RuntimeError(f"Model '{MODEL}' is not downloaded. Run:  ollama pull {MODEL}")
    r.raise_for_status()
    return r.json()["message"]["content"]


def extract_bill(file_bytes: bytes, filename: str) -> Bill:
    text = read_document(file_bytes, filename)
    if len(text.strip()) < 10:
        raise ValueError("No readable text found. Try a sharper, well-lit, flat photo.")

    user = f"OCR text of the bill:\n\n{text}\n\nReturn the JSON."
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]

    try:  # preferred: schema-constrained output
        raw = _chat(messages, fmt=Bill.model_json_schema())
    except requests.HTTPError:  # older Ollama: fall back to plain JSON mode
        hint = "\nUse exactly this JSON schema:\n" + json.dumps(Bill.model_json_schema())
        messages[0]["content"] += hint
        raw = _chat(messages, fmt="json")

    try:
        return Bill.model_validate_json(raw)
    except ValidationError as e:
        raise ValueError(f"The model's output didn't match the expected format. Try again or use a larger model.\n{e}")


# ----------------------------------------------------------------- Q&A
def answer_question(question: str, items_csv: str) -> str:
    """Small local models are bad at arithmetic, so we pre-compute the totals with pandas."""
    df = pd.read_csv(StringIO(items_csv))
    df["month"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m")
    facts = (
        "Spend by category:\n" + df.groupby("category")["total_price"].sum().round(2).to_string() +
        "\n\nSpend by store:\n" + df.groupby("store")["total_price"].sum().round(2).to_string() +
        "\n\nSpend by month:\n" + df.groupby("month")["total_price"].sum().round(2).to_string() +
        "\n\nSpend by category and month:\n" +
        df.groupby(["month", "category"])["total_price"].sum().round(2).to_string() +
        f"\n\nGrand total: {df['total_price'].sum():.2f}"
    )
    system = ("You answer questions about a person's grocery purchases using ONLY the data given. "
              "Use the pre-computed totals; do not recompute sums yourself. Quote numbers exactly. "
              "If the data can't answer the question, say so.")
    user = f"Pre-computed totals:\n{facts}\n\nItem rows (CSV):\n{items_csv}\n\nQuestion: {question}"
    return _chat([{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=800)
