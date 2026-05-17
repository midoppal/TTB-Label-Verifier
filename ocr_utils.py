from PIL import Image
import pytesseract
import cv2
import numpy as np
from io import BytesIO


def load_image(uploaded_file):
    return Image.open(uploaded_file).convert("RGB")


# preprocess to improve image quality
def preprocess_pil_image(image):
    image = image.convert("RGB")
    image_np = np.array(image)

    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)

    gray = cv2.medianBlur(gray, 3)

    processed = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        2
    )

    return image, processed


def preprocess_image(uploaded_file):
    image = load_image(uploaded_file)
    return preprocess_pil_image(image)


# for pdf uploads
def render_pdf_pages(uploaded_file, scale=2):
    try:
        import fitz
    except ImportError as error:
        raise RuntimeError(
            "PDF support requires PyMuPDF. Install project dependencies with "
            "`pip install -r requirements.txt`."
        ) from error

    pdf_document = fitz.open(stream=uploaded_file.getvalue(), filetype="pdf")

    try:
        if pdf_document.needs_pass:
            raise ValueError("Password-protected PDFs are not supported.")

        rendered_pages = []
        matrix = fitz.Matrix(scale, scale)

        for page_index, page in enumerate(pdf_document, start=1):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            page_image = Image.open(BytesIO(pixmap.tobytes("png"))).convert("RGB")
            rendered_pages.append((page_index, page_image))

        return rendered_pages
    finally:
        pdf_document.close()


def extract_text_from_image(processed_image):
    text = pytesseract.image_to_string(processed_image)
    return text


# estimate if the image is blurry
def estimate_image_quality(processed_image):
    blur_score = cv2.Laplacian(processed_image, cv2.CV_64F).var()

    if blur_score < 50:
        return "Low", blur_score, "Image may be blurry. OCR results may be unreliable."
    elif blur_score < 120:
        return "Medium", blur_score, "Image quality is acceptable but may need manual review."
    else:
        return "High", blur_score, "Image appears clear."
