from __future__ import annotations

import io
import os
from functools import lru_cache
from statistics import mean
from typing import List, Tuple

import pytesseract
from PIL import Image, ImageFilter, ImageOps

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

if os.getenv("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD", "")


@lru_cache(maxsize=1)
def _get_easyocr_reader():
    import easyocr

    return easyocr.Reader(["en"], gpu=False)


def _uploaded_file_bytes(uploaded_file) -> bytes:
    if hasattr(uploaded_file, "getvalue"):
        return uploaded_file.getvalue()
    if hasattr(uploaded_file, "read"):
        return uploaded_file.read()
    if isinstance(uploaded_file, (bytes, bytearray)):
        return bytes(uploaded_file)
    raise TypeError("Unsupported upload object")


def _load_images(uploaded_file) -> List[Image.Image]:
    data = _uploaded_file_bytes(uploaded_file)
    filename = getattr(uploaded_file, "name", "").lower()

    if filename.endswith(".pdf") or data[:4] == b"%PDF":
        try:
            import fitz
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("PDF upload detected, but PyMuPDF is not installed.") from exc
        document = fitz.open(stream=data, filetype="pdf")
        images: List[Image.Image] = []
        for page in document:
            matrix = fitz.Matrix(2.0, 2.0)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
            images.append(image)
        return images

    return [Image.open(io.BytesIO(data)).convert("RGB")]


def _preprocess_image(image: Image.Image) -> Image.Image:
    processed = image.convert("L")
    processed = ImageOps.autocontrast(processed)
    processed = processed.filter(ImageFilter.MedianFilter(size=3))
    scale = 2 if max(processed.size) < 2200 else 1
    if scale > 1:
        processed = processed.resize((processed.width * scale, processed.height * scale))
    processed = processed.filter(ImageFilter.SHARPEN)
    processed = processed.point(lambda p: 255 if p > 165 else 0)
    return processed


def _ocr_tesseract(image: Image.Image) -> Tuple[str, List[float]]:
    from utils import log_exception
    
    try:
        text = pytesseract.image_to_string(image, config="--oem 3 --psm 6")
        confidence_values: List[float] = []
        try:
            data = pytesseract.image_to_data(image, config="--oem 3 --psm 6", output_type=pytesseract.Output.DICT)
            for value in data.get("conf", []):
                try:
                    number = float(value)
                    if number >= 0:
                        confidence_values.append(number)
                except Exception:
                    continue
        except Exception:
            pass
        return text.strip(), confidence_values
    except Exception as exc:
        log_exception(f"Tesseract OCR failed: {exc}")
        return "", []


def _ocr_easyocr(image: Image.Image) -> Tuple[str, List[float]]:
    import numpy as np

    reader = _get_easyocr_reader()
    result = reader.readtext(np.array(image), detail=1, paragraph=False)
    text_parts: List[str] = []
    confidence_values: List[float] = []
    for entry in result:
        if len(entry) >= 3:
            text_parts.append(entry[1])
            try:
                confidence_values.append(float(entry[2]) * 100)
            except Exception:
                continue
    return " ".join(text_parts).strip(), confidence_values


def run_ocr_comparison(uploaded_file):
    images = _load_images(uploaded_file)
    tesseract_pages: List[str] = []
    easyocr_pages: List[str] = []
    tesseract_confidence_values: List[float] = []
    easyocr_confidence_values: List[float] = []

    for image in images:
        processed = _preprocess_image(image)
        tesseract_text, tesseract_confidences = _ocr_tesseract(processed)
        easyocr_text, easyocr_confidences = _ocr_easyocr(processed)
        if tesseract_text:
            tesseract_pages.append(tesseract_text)
        if easyocr_text:
            easyocr_pages.append(easyocr_text)
        tesseract_confidence_values.extend(tesseract_confidences)
        easyocr_confidence_values.extend(easyocr_confidences)

    tesseract_raw = "\n\n".join(tesseract_pages).strip()
    easyocr_raw = "\n\n".join(easyocr_pages).strip()

    tesseract_score = (mean(tesseract_confidence_values) if tesseract_confidence_values else 0.0) + (len(tesseract_raw) / 1000.0)
    easyocr_score = (mean(easyocr_confidence_values) if easyocr_confidence_values else 0.0) + (len(easyocr_raw) / 1000.0)

    accuracy_report = {
        "page_count": len(images),
        "tesseract_character_count": len(tesseract_raw),
        "easyocr_character_count": len(easyocr_raw),
        "tesseract_mean_confidence": round(mean(tesseract_confidence_values), 2) if tesseract_confidence_values else None,
        "easyocr_mean_confidence": round(mean(easyocr_confidence_values), 2) if easyocr_confidence_values else None,
        "recommended_engine": "easyocr" if easyocr_score >= tesseract_score else "tesseract",
        "notes": "OCR was run on preprocessed page images to improve results on scans and mobile photos.",
    }

    return tesseract_raw, easyocr_raw, accuracy_report