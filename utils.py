from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "invoice_log.txt"

DATE_INPUT_FORMATS = (
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y-%m-%d",
    "%d/%m/%y",
    "%d-%m-%y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d %Y",
    "%B %d %Y",
)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def safe_float(value: Any) -> Optional[float]:
    text = normalize_text(value)
    if not text:
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", text.replace(",", ""))
    if cleaned in {"", ".", "-", "-."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def safe_int(value: Any) -> Optional[int]:
    number = safe_float(value)
    if number is None:
        return None
    try:
        return int(round(number))
    except Exception:
        return None


def standardize_date(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return ""

    cleaned = text.replace(".", "/").replace("-", "/")
    for fmt in DATE_INPUT_FORMATS:
        try:
            parsed = datetime.strptime(cleaned, fmt.replace("-", "/"))
            return parsed.strftime("%d/%m/%Y")
        except ValueError:
            continue

    digit_groups = re.findall(r"\d+", cleaned)
    if len(digit_groups) >= 3:
        day, month, year = digit_groups[:3]
        if len(year) == 2:
            year = f"20{year}"
        try:
            parsed = datetime(int(year), int(month), int(day))
            if 1900 <= parsed.year <= 2100:
                return parsed.strftime("%d/%m/%Y")
            return ""
        except ValueError:
            return ""

    return ""


def is_plausible_amount(value: Any) -> bool:
    number = safe_float(value)
    if number is None:
        return False
    if number < 0:
        return False
    return number < 1000000


def is_plausible_invoice_number(value: Any) -> bool:
    text = normalize_text(value)
    if not text:
        return False
    if len(text) < 3 or len(text) > 40:
        return False
    return bool(re.search(r"[A-Z0-9]", text, re.IGNORECASE))


def is_valid_gstin(value: Any) -> bool:
    text = normalize_text(value).upper().replace(" ", "")
    if not text:
        return False
    return bool(re.fullmatch(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]", text))


def detect_manual_corrections(original: Dict[str, Any], edited: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    corrections: Dict[str, Dict[str, Any]] = {}
    for key, edited_value in edited.items():
        original_value = normalize_text(original.get(key))
        edited_text = normalize_text(edited_value)
        if original_value != edited_text:
            corrections[key] = {"from": original_value, "to": edited_text}
    return corrections


def _format_dict_for_log(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=True, indent=2, default=str)


def log_activity(message: str, status: str = "INFO") -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] [{status}] {message}\n")


def log_invoice_event(
    upload_name: str,
    fields: Dict[str, Any],
    *,
    exceptions: Optional[Iterable[str]] = None,
    manual_corrections: Optional[Dict[str, Dict[str, Any]]] = None,
) -> None:
    payload = {
        "upload": upload_name,
        "fields": fields,
        "exceptions": list(exceptions or []),
        "manual_corrections": manual_corrections or {},
    }
    log_activity(_format_dict_for_log(payload), status="INVOICE_EVENT")


def log_extraction_details(invoice_no: str, fields: Dict[str, Any]) -> None:
    payload = {"invoice_number": invoice_no, "fields": fields}
    log_activity(_format_dict_for_log(payload), status="DATA_EXTRACTED")


def log_exception(error_msg: str) -> None:
    log_activity(error_msg, status="EXCEPTION")