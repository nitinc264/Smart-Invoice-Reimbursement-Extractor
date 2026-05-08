# Smart Invoice Reimbursement Extractor

An end-to-end **Intelligent Document Processing (IDP)** system that automates invoice data extraction, validation, and reimbursement logging using OCR, AI-powered refinement, and a Human-in-the-Loop verification workflow.

This project is designed to process noisy invoice PDFs and scanned images, extract structured financial data, and maintain an audit-ready Excel database for reimbursement workflows.

---

## 🚀 Features

### 🔍 Dual OCR Engine Pipeline
Uses both **Tesseract OCR** and **EasyOCR** to maximize extraction accuracy across:

- Digital invoices
- Mobile-clicked scans
- Blurry receipts
- Handwritten bills
- Low-quality PDFs

The system compares outputs from both engines to improve reliability.

---

### 🤖 AI-Powered Data Refinement
Integrated with **Google Gemini Pro** for:

- OCR error correction (`O → 0`, `I → 1`, `S → 5`)
- Removing industrial OCR noise
- Cleaning inconsistent invoice formats
- Refining extracted text into structured JSON
- Resolving conflicting OCR outputs

---

### 📄 Smart Financial Field Extraction
Extracts critical invoice fields such as:

- Invoice Number
- Vendor Name
- Invoice Date
- GSTIN
- IRN
- HSN/SAC Codes
- Tax Amount
- Grand Total
- CGST / SGST / IGST
- Payment Details

Special handling is implemented for detecting **Grand Totals** hidden inside complex tax tables.

---

### 🧾 Human-in-the-Loop Verification
Provides manual verification before final submission to ensure:

- Higher extraction accuracy
- Reduced reimbursement errors
- Better audit compliance

---

### 📊 Persistent Excel Database
Validated records are automatically appended to:

```text
reimbursement_invoices.xlsx
```

Features include:

- Auto-incrementing invoice IDs
- Timestamp tracking
- Persistent storage
- Structured reimbursement records

---

### 📜 Invoice Audit Logging
Maintains a detailed:

```text
invoice_log.txt
```

Tracks:

- Upload activity
- OCR exceptions
- Processing errors
- Manual corrections
- Validation history

---

## 🛠️ Tech Stack

| Category | Technologies |
|---|---|
| Interface | Streamlit |
| OCR Engines | Tesseract OCR, EasyOCR |
| AI / LLM | Google Gemini Pro |
| Data Processing | Pandas |
| Excel Handling | Openpyxl |
| PDF Processing | PyMuPDF |
| Image Processing | Pillow |
| Utilities | Python Logging, Regex |

---

## 📂 Project Structure

```text
Smart-Invoice-Reimbursement-Extractor/
│
├── app.py
│   ├── Streamlit UI
│   └── Main application workflow
│
├── processor.py
│   ├── Prompt engineering
│   ├── Gemini refinement logic
│   └── Data normalization
│
├── ocr_engines.py
│   ├── Tesseract OCR pipeline
│   ├── EasyOCR pipeline
│   └── Image preprocessing
│
├── excel_handler.py
│   ├── Excel database creation
│   ├── Record appending
│   └── Timestamp handling
│
├── utils.py
│   ├── Logging utilities
│   ├── Validation helpers
│   └── Text cleanup functions
│
├── samples/
│   ├── Digital invoices
│   └── Handwritten invoice samples
│
├── requirements.txt
│
├── packages.txt
│
└── README.md
```

---

## ⚙️ Installation & Setup

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/nitinc264/Smart-Invoice-Reimbursement-Extractor.git

cd Smart-Invoice-Reimbursement-Extractor
```

---

### 2️⃣ Install Python Dependencies

```bash
pip install -r requirements.txt
```

---

### 3️⃣ Install Tesseract OCR

Download and install Tesseract OCR:

#### Windows
Install from the official installer.

#### Linux

```bash
sudo apt install tesseract-ocr
```

#### Mac

```bash
brew install tesseract
```

Ensure Tesseract is added to your system PATH.

---

### 4️⃣ Configure Environment Variables

Create a `.env` file:

```env
GOOGLE_API_KEY=your_gemini_api_key
```

---

### 5️⃣ Run the Application

```bash
streamlit run app.py
```

---

## 📌 Workflow

```text
Invoice Upload
      ↓
Image/PDF Preprocessing
      ↓
Tesseract OCR + EasyOCR
      ↓
OCR Comparison & Merging
      ↓
Gemini AI Refinement
      ↓
Field Extraction
      ↓
Human Verification
      ↓
Excel Database Update
      ↓
Audit Logging
```

---


## 🧪 Sample Use Cases

- Employee reimbursement automation
- GST invoice management
- Expense tracking systems
- Financial audit preparation
- OCR benchmarking research
- AI-assisted document processing

---

## 🔮 Future Improvements

- Multi-language invoice support
- Table structure recognition
- QR code invoice parsing
- Database integration (PostgreSQL/MySQL)
- REST API support
- Batch invoice processing
- Confidence scoring dashboard
- Docker deployment

---

## 📄 License

This project is licensed under the MIT License.

---
