from PIL import Image
import pytesseract
import cv2
import numpy as np


def preprocess_image(uploaded_file):
    image = Image.open(uploaded_file).convert("RGB")
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


def extract_text_from_image(processed_image):
    text = pytesseract.image_to_string(processed_image)
    return text


def estimate_image_quality(processed_image):
    blur_score = cv2.Laplacian(processed_image, cv2.CV_64F).var()

    if blur_score < 50:
        return "Low", blur_score, "Image may be blurry. OCR results may be unreliable."
    elif blur_score < 120:
        return "Medium", blur_score, "Image quality is acceptable but may need manual review."
    else:
        return "High", blur_score, "Image appears clear."