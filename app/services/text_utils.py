# app/services/text_utils.py
import os
import json
import csv
import re
from typing import List, Any, Dict
from pathlib import Path
from PyPDF2 import PdfReader
import docx
import openpyxl
from PIL import Image
import pytesseract

# Optional OCR imports
_OCR_AVAILABLE = False
try:
    
    _OCR_AVAILABLE = True
except Exception:
    _OCR_AVAILABLE = False


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff"}
DOCX_EXTS = {".docx"}
XLSX_EXTS = {".xlsx"}
TEXT_EXTS = {".txt", ".md", ".log"}
CSV_EXTS  = {".csv"}
JSON_EXTS = {".json"}
PDF_EXTS  = {".pdf"}
# Old binary .doc and .xls are tricky; we attempt best-effort fallback
LEGACY_DOC_EXTS = {".doc"}
LEGACY_XLS_EXTS = {".xls"}
SVG_EXTS = {".svg"}

def _flatten_json(data: Any, prefix: str = "") -> List[str]:
    out = []
    if isinstance(data, dict):
        for k, v in data.items():
            key = f"{prefix}.{k}" if prefix else k
            out.extend(_flatten_json(v, key))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            key = f"{prefix}[{i}]"
            out.extend(_flatten_json(v, key))
    else:
        out.append(f"{prefix}: {data}")
    return out

def _extract_from_pdf(path: str) -> str:
    text = ""
    reader = PdfReader(path)
    for p in reader.pages:
        text += p.extract_text() or ""
    return text

def _extract_from_docx(path: str) -> str:
    d = docx.Document(path)
    return "\n".join(para.text for para in d.paragraphs if para.text)

def _extract_from_xlsx(path: str) -> str:
    wb = openpyxl.load_workbook(path, data_only=True)
    parts = []
    for sheet in wb.worksheets:
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)

def _extract_from_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def _extract_from_csv(path: str) -> str:
    parts = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                parts.append(", ".join(row))
    return "\n".join(parts)

def _extract_from_json(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        data = json.load(f)
    flat = _flatten_json(data)
    return "\n".join(flat)

def _extract_from_svg(path: str) -> str:
    # crude: strip tags to get text nodes
    raw = _extract_from_txt(path)
    return re.sub(r"<[^>]+>", " ", raw)

def _extract_from_image(path: str) -> str:
    if not _OCR_AVAILABLE:
        return ""  # graceful: no OCR installed
    try:
        img = Image.open(path)
        # You can tweak config if needed for accuracy
        return pytesseract.image_to_string(img)
    except Exception:
        return ""

def extract_text_from_file(path: str, content_type: str) -> str:
    ext = Path(path).suffix.lower()
    try:
        if ext in PDF_EXTS:
            return _extract_from_pdf(path)
        if ext in DOCX_EXTS:
            return _extract_from_docx(path)
        if ext in XLSX_EXTS:
            return _extract_from_xlsx(path)
        if ext in TEXT_EXTS:
            return _extract_from_txt(path)
        if ext in CSV_EXTS:
            return _extract_from_csv(path)
        if ext in JSON_EXTS:
            return _extract_from_json(path)
        if ext in SVG_EXTS:
            return _extract_from_svg(path)
        if ext in IMAGE_EXTS:
            return _extract_from_image(path)

        # Legacy formats: best-effort fallbacks
        if ext in LEGACY_DOC_EXTS:
            # try docx parser anyway (many .doc files won't work)
            try:
                return _extract_from_docx(path)
            except Exception:
                return ""  # silently skip if unreadable
        if ext in LEGACY_XLS_EXTS:
            # we don't add xlrd dependency; fallback to plain text
            return _extract_from_txt(path)

        # default fallback as plain text
        return _extract_from_txt(path)
    except Exception:
        # never crash extraction
        return ""

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    if not text:
        return []
    chunks = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        chunk = text[start:end]
        chunks.append(chunk.strip())
        if end == length:
            break
        start = max(0, end - overlap)
    return [c for c in chunks if c]
