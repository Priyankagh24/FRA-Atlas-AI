import io
import os
from PIL import Image

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    pytesseract = None
    TESSERACT_AVAILABLE = False

try:
    import fitz
    PDF_SUPPORT = True
except ImportError:
    fitz = None
    PDF_SUPPORT = False

if TESSERACT_AVAILABLE and os.name == "nt":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_text_from_pdf(file_bytes: bytes) -> str:
    if not PDF_SUPPORT:
        return "PDF OCR not available on this server"
    if not TESSERACT_AVAILABLE:
        return "OCR not available on this server"
    try:
        pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
        if pdf_document.page_count == 0:
            raise RuntimeError("PDF contains no readable pages")
        page_texts = []
        for page_index in range(min(3, pdf_document.page_count)):
            page = pdf_document[page_index]
            pix = page.get_pixmap(dpi=200, alpha=False)
            image_bytes = pix.tobytes("png")
            image = Image.open(io.BytesIO(image_bytes))
            page_texts.append(pytesseract.image_to_string(image, lang="eng"))
        return "\n".join(page_texts).strip()
    except Exception as e:
        raise RuntimeError(f"PDF OCR extraction failed: {e}")


def extract_text_from_file(file_bytes: bytes) -> str:
    if not file_bytes:
        raise RuntimeError("No file content provided for OCR")
    if not TESSERACT_AVAILABLE:
        return "OCR not available on this server"
    head = file_bytes[:20]
    if head.startswith(b"%PDF") or b"/Type /Page" in head:
        return extract_text_from_pdf(file_bytes)
    try:
        image = Image.open(io.BytesIO(file_bytes))
        text = pytesseract.image_to_string(image, lang="eng")
        return text.strip()
    except Exception as e:
        if PDF_SUPPORT and head.startswith(b"%PDF"):
            return extract_text_from_pdf(file_bytes)
        raise RuntimeError(f"OCR extraction failed: {str(e)}")
