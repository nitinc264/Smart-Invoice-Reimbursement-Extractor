from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Any, Dict, Optional

import google.generativeai as genai

from utils import normalize_text, safe_float, safe_int, standardize_date

FIELD_ORDER = [
    "invoice_number",
    "vendor",
    "date",
    "total",
    "gst",
    "item_desc",
    "qty",
    "price",
    "tax",
    "net_payable",
    "payment_mode",
    "customer_name",
]


PROMPT_TEMPLATE = """
You are a senior document understanding engine for invoice reimbursement extraction.

Goal:
- Reconcile two OCR sources from the same invoice: Tesseract and EasyOCR.
- Correct obvious OCR confusion only when context supports it, including O/0, I/1, 8/B, S/5, and l/1.
- Remove noise, headers, footers, and broken fragments.
- Standardize all dates to DD/MM/YYYY.
- Return a single valid JSON object only.
- Assign a confidence_score (0-100) indicating your confidence in the overall extraction quality.

Aggressive Total Finding:
- Search specifically for values near labels: "Grand Total", "Total Amount", "Net Payable", and "Total Invoice Value".
- If multiple total-like values are found, select the largest currency amount that is not a GST/Tax component.
- Treat numbers near labels like "GST", "CGST", "SGST", "IGST", "Tax", or "%" as tax values, not the final invoice total.

Noise Filtering for Invoice Number:
- Fragments like "i639" and other short alphanumeric snippets are likely OCR noise from IRN/GST zones.
- Do NOT use such snippets as invoice_number.
- Prefer invoice_number values found near explicit labels: "Invoice No.", "Invoice Number", "Bill No.", or "Bill Number".
- If no reliable label-bound value is found, return null for invoice_number and include the reason in confidence_notes.

Contextual Validation and OCR Repair:
- If OCR confusion appears (example: S instead of 5, O instead of 0), fix to the most logical value using invoice context.
- Use table/amount consistency checks for qty, price, tax, total, and net_payable.
- Date values must be realistic and valid; reject impossible day/month combinations.

Critical Instructions for Vendor Field:
- Extract ONLY the official business name. DO NOT include license numbers (e.g., PLB-80063, EST1), dates, or registration IDs.
- Remove anything after a comma that contains numbers and abbreviations (e.g., "(GOVT, RECOGNISED)" should be stripped).
- If the vendor name is broken across lines, combine them logically.

Critical Instructions for Date Field:
- Strictly validate dates against the document context. If you see "66-68-2028", reject it as invalid.
- Check if month and day are plausible (1-12 and 1-31 respectively).
- If the year appears hallucinated or impossible (e.g., 66, 68), use the current year 2026 as fallback.
- Never output impossible dates; use null if date cannot be confidently parsed.

Industrial Specifics (IRN/GSTIN/HSN-SAC):
- Look for IRN values: long 64-character hexadecimal-like strings.
- Look for GSTIN values: 15-character alphanumeric strings starting with state code digits (e.g., 27...).
- Look for HSN/SAC codes in item/line descriptions (typically 6-8 digit codes).
- Put these in metadata fields when available:
    metadata.irn, metadata.gstin, metadata.hsn_sac_codes

Rules:
- Use null for missing values.
- If values conflict, keep the most likely one and list the issue in conflicting_fields.
- missing_fields must list any field that could not be confidently extracted.
- Output numeric fields as numbers when possible.
- confidence_score must be an integer 0-100, where 100 = perfect extraction, 0 = all fields missing/invalid.

Required keys:
invoice_number, vendor, date, total, gst, item_desc, qty, price, tax, net_payable, payment_mode, customer_name, missing_fields, conflicting_fields, confidence_notes, confidence_score

Optional key:
metadata (object with optional keys: irn, gstin, hsn_sac_codes)

Tesseract OCR:
{tesseract_text}

EasyOCR OCR:
{easyocr_text}
""".strip()


def _extract_json_block(text: str) -> str:
    cleaned = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1)

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned


def _normalize_money(value: Any) -> Optional[float]:
    return safe_float(value)


def _normalize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    normalized = {field: None for field in FIELD_ORDER}
    normalized.update(record if isinstance(record, dict) else {})
    normalized["date"] = standardize_date(normalized.get("date"))
    normalized["qty"] = safe_int(normalized.get("qty"))
    normalized["total"] = _normalize_money(normalized.get("total"))
    normalized["price"] = _normalize_money(normalized.get("price"))
    normalized["tax"] = _normalize_money(normalized.get("tax"))
    normalized["net_payable"] = _normalize_money(normalized.get("net_payable"))
    normalized["vendor"] = normalize_text(normalized.get("vendor"))
    normalized["invoice_number"] = normalize_text(normalized.get("invoice_number"))
    normalized["gst"] = normalize_text(normalized.get("gst"))
    normalized["item_desc"] = normalize_text(normalized.get("item_desc"))
    normalized["payment_mode"] = normalize_text(normalized.get("payment_mode"))
    normalized["customer_name"] = normalize_text(normalized.get("customer_name"))
    normalized["confidence_score"] = record.get("confidence_score", 50) if isinstance(record, dict) else 50
    return normalized


def _coerce_confidence(value: Any, default: int = 50) -> int:
    if isinstance(value, (int, float)):
        return max(0, min(100, int(value)))
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        if match:
            return max(0, min(100, int(match.group(0))))
    return default


def _build_fallback_record(tesseract_text: str, easyocr_text: str) -> Dict[str, Any]:
    combined = f"{tesseract_text}\n{easyocr_text}".strip()
    upper = combined.upper()

    invoice_number = None
    for pattern in [r"(?:INV(?:OICE)?\s*(?:NO|NUMBER|#)[:\-\s]*)\s*([A-Z0-9\-/]+)", r"\b([A-Z]{1,4}[\-/]?[0-9]{3,})\b"]:
        match = re.search(pattern, combined, re.IGNORECASE)
        if match:
            invoice_number = match.group(1).strip()
            break

    gst_match = re.search(r"\b[0-9]{2}[A-Z0-9]{13}\b", upper)
    date_match = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", combined)
    payment_mode = None
    for candidate in ["UPI", "CASH", "BANK", "CARD", "CHEQUE", "NET BANKING"]:
        if candidate in upper:
            payment_mode = candidate.title() if candidate != "UPI" else "UPI"
            break

    number_candidates = [float(value) for value in re.findall(r"\b\d+(?:\.\d+)?\b", combined) if value]
    total = max(number_candidates) if number_candidates else None

    record = {
        "invoice_number": invoice_number,
        "vendor": None,
        "date": standardize_date(date_match.group(1)) if date_match else None,
        "total": total,
        "gst": gst_match.group(0) if gst_match else None,
        "item_desc": None,
        "qty": None,
        "price": None,
        "tax": None,
        "net_payable": None,
        "payment_mode": payment_mode,
        "customer_name": None,
        "missing_fields": [],
        "conflicting_fields": [],
        "confidence_notes": "Fallback extraction was used because the Gemini response could not be parsed.",
    }
    record["missing_fields"] = [field for field in FIELD_ORDER if not record.get(field)]
    return record


@lru_cache(maxsize=1)
def _get_model():
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash")


def clean_with_llm(tesseract_text: str, easyocr_text: str) -> Dict[str, Any]:
    return extract_invoice_data(tesseract_text, easyocr_text)


def extract_invoice_data(tesseract_text: str, easyocr_text: str) -> Dict[str, Any]:
    model = _get_model()
    if model is None:
        return _build_fallback_record(tesseract_text, easyocr_text)

    prompt = PROMPT_TEMPLATE.format(tesseract_text=tesseract_text, easyocr_text=easyocr_text)

    try:
        response = model.generate_content(prompt)
        response_text = getattr(response, "text", "") or ""
        parsed = json.loads(_extract_json_block(response_text))
        if isinstance(parsed, dict):
            parsed.setdefault("missing_fields", [])
            parsed.setdefault("conflicting_fields", [])
            parsed.setdefault("confidence_notes", "")
            parsed.setdefault("confidence_score", 50)
            parsed.setdefault("metadata", {})
            normalized = _normalize_record(parsed)
            normalized["missing_fields"] = parsed.get("missing_fields", []) if isinstance(parsed.get("missing_fields"), list) else []
            normalized["conflicting_fields"] = parsed.get("conflicting_fields", []) if isinstance(parsed.get("conflicting_fields"), list) else []
            normalized["confidence_notes"] = normalize_text(parsed.get("confidence_notes"))
            normalized["confidence_score"] = _coerce_confidence(parsed.get("confidence_score"), default=50)
            normalized["metadata"] = parsed.get("metadata") if isinstance(parsed.get("metadata"), dict) else {}
            normalized["raw_model_response"] = response_text
            return normalized
    except Exception:
        pass

    fallback = _build_fallback_record(tesseract_text, easyocr_text)
    fallback["raw_model_response"] = ""
    return fallback