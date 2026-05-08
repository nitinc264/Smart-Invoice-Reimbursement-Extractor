from __future__ import annotations

from typing import Any, Dict

import streamlit as st

from excel_handler import save_to_excel
from ocr_engines import run_ocr_comparison
from processor import clean_with_llm
from utils import detect_manual_corrections, log_exception, log_invoice_event, normalize_text, safe_float, safe_int, standardize_date

st.set_page_config(page_title="Smart Invoice Reimbursement Extractor", layout="wide")
st.title("Smart Invoice Reimbursement Extractor")
st.caption("Upload a PDF, JPG, PNG, or JPEG invoice, review the extracted values, and save the cleaned record to Excel.")

FIELD_LABELS = [
    ("invoice_number", "Invoice Number"),
    ("vendor", "Vendor"),
    ("date", "Date"),
    ("total", "Total"),
    ("gst", "GST"),
    ("item_desc", "Item Desc"),
    ("qty", "Qty"),
    ("price", "Price"),
    ("tax", "Tax"),
    ("net_payable", "Net Payable"),
    ("payment_mode", "Payment Mode"),
    ("customer_name", "Customer Name"),
]


def _default_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _build_review_map(extracted: Dict[str, Any]) -> Dict[str, bool]:
    review_fields = set(map(str, extracted.get("missing_fields", []))) | set(map(str, extracted.get("conflicting_fields", [])))
    return {field: field in review_fields for field, _ in FIELD_LABELS}


uploaded_file = st.file_uploader("Upload invoice file", type=["pdf", "jpg", "jpeg", "png"])

if uploaded_file:
    file_name = uploaded_file.name

    if "ocr_result" not in st.session_state or st.session_state.get("uploaded_name") != file_name:
        try:
            with st.spinner("Running OCR comparison..."):
                tesseract_text, easyocr_text, accuracy_report = run_ocr_comparison(uploaded_file)

            with st.spinner("Cleaning OCR output with Gemini..."):
                extracted_data = clean_with_llm(tesseract_text, easyocr_text)

            st.session_state["uploaded_name"] = file_name
            st.session_state["ocr_result"] = {
                "tesseract_text": tesseract_text,
                "easyocr_text": easyocr_text,
                "accuracy_report": accuracy_report,
                "extracted_data": extracted_data,
            }
        except Exception as exc:
            log_exception(str(exc))
            st.error(f"Processing failed: {exc}")
            st.stop()

    ocr_result = st.session_state["ocr_result"]
    extracted_data = ocr_result["extracted_data"]
    review_map = _build_review_map(extracted_data)

    c1, c2, c3 = st.columns(3)
    c1.metric("OCR Pages", ocr_result["accuracy_report"].get("page_count", 0))
    c2.metric("Recommended Engine", ocr_result["accuracy_report"].get("recommended_engine", "n/a").title())
    c3.metric("Date Format", "DD/MM/YYYY")

    if not ocr_result["accuracy_report"].get("tesseract_available", True):
        st.warning("Tesseract is not installed or not on PATH in this environment, so the comparison feature is using EasyOCR only for the Tesseract side.")

    if extracted_data.get("missing_fields"):
        st.warning("Missing fields need confirmation: " + ", ".join(map(str, extracted_data["missing_fields"])))
    if extracted_data.get("conflicting_fields"):
        st.warning("Conflicting fields need confirmation: " + ", ".join(map(str, extracted_data["conflicting_fields"])))

    review_tab, comparison_tab, raw_tab = st.tabs(["Structured Review", "Comparison", "Raw OCR"])

    with comparison_tab:
        st.subheader("OCR Comparison")
        st.json(ocr_result["accuracy_report"])

    with raw_tab:
        left, right = st.columns(2)
        with left:
            st.text_area("Tesseract Raw Text", ocr_result["tesseract_text"], height=320)
        with right:
            st.text_area("EasyOCR Raw Text", ocr_result["easyocr_text"], height=320)

    with review_tab:
        st.subheader("Review and edit the extracted invoice data")
        if extracted_data.get("confidence_score"):
            st.info(f"🎯 Extraction Confidence: {extracted_data.get('confidence_score')}%")

        with st.form("invoice_form"):
            col1, col2 = st.columns(2)
            with col1:
                invoice_number = st.text_input("Invoice Number", value=_default_text(extracted_data.get("invoice_number")), help="Flagged for review" if review_map["invoice_number"] else None)
                vendor = st.text_input("Vendor", value=_default_text(extracted_data.get("vendor")), help="Flagged for review" if review_map["vendor"] else None)
                date = st.text_input("Date", value=_default_text(extracted_data.get("date")), help="Use DD/MM/YYYY")
                total = st.text_input("Total", value=_default_text(extracted_data.get("total")), help="Flagged for review" if review_map["total"] else None)
                gst = st.text_input("GST", value=_default_text(extracted_data.get("gst")), help="Flagged for review" if review_map["gst"] else None)
                customer_name = st.text_input("Customer Name", value=_default_text(extracted_data.get("customer_name")), help="Flagged for review" if review_map["customer_name"] else None)

            with col2:
                item_desc = st.text_area("Item Desc", value=_default_text(extracted_data.get("item_desc")), height=120, help="Flagged for review" if review_map["item_desc"] else None)
                qty = st.text_input("Qty", value=_default_text(extracted_data.get("qty")), help="Flagged for review" if review_map["qty"] else None)
                price = st.text_input("Price", value=_default_text(extracted_data.get("price")), help="Flagged for review" if review_map["price"] else None)
                tax = st.text_input("Tax", value=_default_text(extracted_data.get("tax")), help="Flagged for review" if review_map["tax"] else None)
                net_payable = st.text_input("Net Payable", value=_default_text(extracted_data.get("net_payable")), help="Flagged for review" if review_map["net_payable"] else None)
                payment_mode = st.text_input("Payment Mode", value=_default_text(extracted_data.get("payment_mode")), help="Flagged for review" if review_map["payment_mode"] else None)

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                save_clicked = st.form_submit_button("💾 Save to Excel")
            with col_btn2:
                clear_clicked = st.form_submit_button("🔄 Clear All")

            if clear_clicked:
                st.session_state.pop("ocr_result", None)
                st.session_state.pop("uploaded_name", None)
                st.success("Form cleared. Ready for next upload.")
                st.rerun()

            if save_clicked:
                edited_record = {
                    "Invoice Number": normalize_text(invoice_number),
                    "Vendor": normalize_text(vendor),
                    "Date": standardize_date(date),
                    "Total": safe_float(total),
                    "GST": normalize_text(gst),
                    "Item Desc": normalize_text(item_desc),
                    "Qty": safe_int(qty),
                    "Price": safe_float(price),
                    "Tax": safe_float(tax),
                    "Net Payable": safe_float(net_payable),
                    "Payment Mode": normalize_text(payment_mode),
                    "Customer Name": normalize_text(customer_name),
                }

                original_record = {
                    "Invoice Number": extracted_data.get("invoice_number"),
                    "Vendor": extracted_data.get("vendor"),
                    "Date": extracted_data.get("date"),
                    "Total": extracted_data.get("total"),
                    "GST": extracted_data.get("gst"),
                    "Item Desc": extracted_data.get("item_desc"),
                    "Qty": extracted_data.get("qty"),
                    "Price": extracted_data.get("price"),
                    "Tax": extracted_data.get("tax"),
                    "Net Payable": extracted_data.get("net_payable"),
                    "Payment Mode": extracted_data.get("payment_mode"),
                    "Customer Name": extracted_data.get("customer_name"),
                }

                corrections = detect_manual_corrections(original_record, edited_record)
                success, message = save_to_excel(edited_record)

                if success:
                    st.toast("✅ " + message, icon="✅")
                    st.success(message)
                    log_invoice_event(file_name, edited_record, exceptions=extracted_data.get("conflicting_fields", []), manual_corrections=corrections)
                    if corrections:
                        st.info("📝 Manual corrections were logged for this upload.")
                    st.session_state.pop("ocr_result", None)
                    st.session_state.pop("uploaded_name", None)
                else:
                    if "Duplicate" in message:
                        st.warning("⚠️ " + message)
                    else:
                        st.error(message)
                    log_exception(message)