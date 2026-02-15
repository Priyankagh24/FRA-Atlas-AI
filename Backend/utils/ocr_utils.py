from PIL import Image
import pytesseract
import io
from datetime import datetime


# ✅ Explicitly tell pytesseract where Tesseract is installed (Windows fix)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_text_from_file(file_bytes: bytes) -> str:
    """
    Extract text from an uploaded image file (bytes) using Tesseract OCR.
    Supports PNG, JPG, JPEG, etc.
    """
    try:
        # Open the uploaded file as an image
        image = Image.open(io.BytesIO(file_bytes))

        # Perform OCR with English language
        text = pytesseract.image_to_string(image, lang="eng")

        return text.strip()

    except Exception as e:
        # Return clean error message if OCR fails
        raise RuntimeError(f"OCR extraction failed: {str(e)}")
