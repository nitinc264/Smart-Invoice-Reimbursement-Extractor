from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple
import shutil
import time
import zipfile

import pandas as pd

from utils import normalize_text, safe_float, safe_int, standardize_date

FILE_NAME = Path(__file__).resolve().parent / "reimbursement_invoices.xlsx"

EXCEL_COLUMNS = [
    "Record ID",
    "Timestamp",
    "Invoice Number",
    "Vendor",
    "Date",
    "Total",
    "GST",
    "Item Desc",
    "Qty",
    "Price",
    "Tax",
    "Net Payable",
    "Payment Mode",
    "Customer Name",
]


def _normalize_row(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "Invoice Number": normalize_text(data.get("Invoice Number") or data.get("invoice_number")),
        "Vendor": normalize_text(data.get("Vendor") or data.get("vendor")),
        "Date": standardize_date(data.get("Date") or data.get("date")),
        "Total": safe_float(data.get("Total") or data.get("total")),
        "GST": normalize_text(data.get("GST") or data.get("gst")),
        "Item Desc": normalize_text(data.get("Item Desc") or data.get("item_desc")),
        "Qty": safe_int(data.get("Qty") or data.get("qty")),
        "Price": safe_float(data.get("Price") or data.get("price")),
        "Tax": safe_float(data.get("Tax") or data.get("tax")),
        "Net Payable": safe_float(data.get("Net Payable") or data.get("net_payable")),
        "Payment Mode": normalize_text(data.get("Payment Mode") or data.get("payment_mode")),
        "Customer Name": normalize_text(data.get("Customer Name") or data.get("customer_name")),
    }


def check_duplicate(invoice_no: str) -> Tuple[bool, str]:
    """Check if invoice number already exists in the workbook."""
    if not invoice_no or not invoice_no.strip():
        return False, "Invoice Number is required."
    
    try:
        if FILE_NAME.exists():
            try:
                existing = pd.read_excel(FILE_NAME, engine='openpyxl')
            except Exception as exc:
                # If the existing workbook is corrupted or not an xlsx, back it up and continue with empty
                if "zip" in str(exc).lower() or isinstance(exc, zipfile.BadZipFile):
                    ts = int(time.time())
                    backup = FILE_NAME.with_name(f"{FILE_NAME.stem}.corrupt.{ts}{FILE_NAME.suffix}")
                    shutil.move(str(FILE_NAME), str(backup))
                    existing = pd.DataFrame(columns=EXCEL_COLUMNS)
                else:
                    return False, f"Error checking duplicates: {exc}"

            invoice_numbers = existing["Invoice Number"].astype(str).str.strip().str.lower()
            if invoice_no.strip().lower() in set(invoice_numbers.dropna()):
                return True, f"Duplicate found: Invoice {invoice_no} already exists in the system."
        return False, ""
    except Exception as exc:
        return False, f"Error checking duplicates: {exc}"


def save_to_excel(data: Dict[str, Any]) -> Tuple[bool, str]:
    try:
        row = _normalize_row(data)
        if not row["Invoice Number"]:
            return False, "Invoice Number is required before saving."

        is_duplicate, dup_msg = check_duplicate(row["Invoice Number"])
        if is_duplicate:
            return False, dup_msg

        if FILE_NAME.exists():
            try:
                existing = pd.read_excel(FILE_NAME, engine='openpyxl')
            except Exception as exc:
                if "zip" in str(exc).lower() or isinstance(exc, zipfile.BadZipFile):
                    ts = int(time.time())
                    backup = FILE_NAME.with_name(f"{FILE_NAME.stem}.corrupt.{ts}{FILE_NAME.suffix}")
                    shutil.move(str(FILE_NAME), str(backup))
                    existing = pd.DataFrame(columns=EXCEL_COLUMNS)
                else:
                    return False, f"System Error: {exc}"
        else:
            existing = pd.DataFrame(columns=EXCEL_COLUMNS)

        for column in EXCEL_COLUMNS:
            if column not in existing.columns:
                existing[column] = pd.NA

        if existing.empty:
            next_id = 1
        else:
            max_record_id = pd.to_numeric(existing["Record ID"], errors="coerce").max()
            next_id = 1 if pd.isna(max_record_id) else int(max_record_id) + 1
        row_to_save = {
            "Record ID": next_id,
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            **row,
        }

        updated = pd.concat([existing[EXCEL_COLUMNS], pd.DataFrame([row_to_save], columns=EXCEL_COLUMNS)], ignore_index=True)
        # Write atomically to avoid leaving a corrupt file
        tmp = FILE_NAME.with_suffix(".tmp.xlsx")
        updated.to_excel(tmp, index=False, engine='openpyxl')
        shutil.move(str(tmp), str(FILE_NAME))
        return True, f"Invoice {row['Invoice Number']} saved successfully."
    except Exception as exc:
        return False, f"System Error: {exc}"