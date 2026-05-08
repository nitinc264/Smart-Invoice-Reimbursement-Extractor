Assignment 3: Smart Invoice Reimbursement Extractor

Objective:
Build a complete system where a user uploads any invoice (PDF/image) and the system automatically:
- Reads the invoice
- Extracts key fields
- Standardizes them in a fixed format
- Appends each record to a master Excel file
- Handles errors, duplicates, and missing fields
- Logs all activities

Technical Requirements

1. Input:
- User uploads an invoice in PDF, JPG, PNG formats.
- System must support single-page & multi-page invoices.
- Must handle scanned, low-quality, mobile-clicked invoices.

2. Data Extraction Fields:
Intern must extract the following fields accurately:
- Invoice Number
- Vendor Name
- Invoice Date (DD/MM/YYYY)
- Total Amount
- GST Number
- Item Description
- Item Quantity
- Price Per Item
- Tax Amount (GST/CGST/SGST)
- Net Payable Amount
- Payment Mode (Cash/UPI/Bank)
- Customer Name

3. Output:
- Every uploaded invoice gets appended as one row in reimbursement_invoices.xlsx
- Sheet format: predefined columns (no change allowed)
- System must create the file if it doesn’t exist

4. Mandatory Features:

A) OCR Requirement:
- Compare at least two OCR engines: Tesseract and EasyOCR or Google Vision API
- Provide screenshots and OCR accuracy report

B) Data Validation Rules:
- If values are missing → ask user for confirmation
- Conflicting values → ask user to choose correct one
- Duplicate invoice number → reject entry

C) Prompt Engineering:
Create an LLM prompt to fix OCR errors:
- Character confusion (O/0, I/1, 8/B)
- Wrong currency symbols
- Noise cleanup
Provide before → after proof

D) Excel Writing Logic:
- Append as a new row (never overwrite)
- Auto-increment record ID
- Timestamp column
- Use openpyxl or pandas

E) Logging:
Maintain invoice_log.txt with:
- Upload time
- Extracted fields
- Exceptions
- Wrong formats
- Manual corrections

F) UI Requirement:
Using Streamlit or Flask (bonus: drag & drop):
- Display extracted fields
- Allow edit before saving
- Include “Save to Excel” button

