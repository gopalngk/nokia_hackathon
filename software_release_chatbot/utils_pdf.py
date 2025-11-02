# utils_pdf.py
import io
import fitz  # PyMuPDF
import pdfplumber
from pdfminer.high_level import extract_text as pdfminer_extract
from pypdf import PdfReader  # modern fork of PyPDF2
from PIL import Image
import pytesseract

def _normalize_text(txt: str) -> str:
    if not txt:
        return ""
    # collapse whitespace, keep Unicode
    return " ".join(txt.replace("\u00ad", "").split())

def extract_with_pymupdf(path: str) -> str:
    try:
        text_parts = []
        with fitz.open(path) as doc:
            for page in doc:
                t = page.get_text("text")
                text_parts.append(t or "")
        return _normalize_text("\n".join(text_parts))
    except Exception:
        return ""

def extract_with_pdfplumber(path: str) -> str:
    try:
        text_parts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                text_parts.append(t)
        return _normalize_text("\n".join(text_parts))
    except Exception:
        return ""

def extract_with_pdfminer(path: str) -> str:
    try:
        txt = pdfminer_extract(path)
        return _normalize_text(txt)
    except Exception:
        return ""

def extract_with_pypdf(path: str) -> str:
    try:
        reader = PdfReader(path)
        # Handle encryption
        if reader.is_encrypted:
            try:
                reader.decrypt("")  # try empty password
            except Exception:
                return ""
        text_parts = []
        for page in reader.pages:
            t = page.extract_text() or ""
            text_parts.append(t)
        return _normalize_text("\n".join(text_parts))
    except Exception:
        return ""

def page_is_image_only(page) -> bool:
    # For pdfplumber page: if no extracted text and images present, treat as image-only
    try:
        t = page.extract_text()
        imgs = page.images or []
        return (not t or len(_normalize_text(t)) < 10) and len(imgs) > 0
    except Exception:
        return False

def ocr_with_tesseract(path: str, dpi: int = 300) -> str:
    """OCR pages that appear image-only using pdfplumber -> PIL -> Tesseract."""
    try:
        out_parts = []
        with pdfplumber.open(path) as pdf:
            for p in pdf.pages:
                # Render page to image
                im = p.to_image(resolution=dpi).original
                if not isinstance(im, Image.Image):
                    # Convert to PIL Image if needed
                    im = Image.open(io.BytesIO(im))
                txt = pytesseract.image_to_string(im, lang="eng")
                out_parts.append(txt or "")
        return _normalize_text("\n".join(out_parts))
    except Exception:
        return ""

def robust_extract_pdf(path: str) -> str:
    # 1) Structured parsers
    for func in (extract_with_pymupdf, extract_with_pdfplumber, extract_with_pdfminer, extract_with_pypdf):
        txt = func(path)
        if txt and len(txt) > 50:
            return txt

    # 2) OCR fallback for image-only or stubborn PDFs
    ocr_txt = ocr_with_tesseract(path)
    if ocr_txt and len(ocr_txt) > 50:
        return ocr_txt

    # 3) Last resort: empty
    return ""
