from PIL import Image
import pytesseract
import cv2
import numpy as np


def preprocess_image(uploaded_file):
    """
    Preprocess uploaded image to improve OCR quality.
    Steps:
    - Convert image to RGB
    - Convert to grayscale
    - Denoise lightly
    - Apply thresholding
    """
    image = Image.open(uploaded_file).convert("RGB")
    image_np = np.array(image)

    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)

    # Light denoising
    gray = cv2.medianBlur(gray, 3)

    # Improve contrast with adaptive thresholding
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
    """
    Run OCR on the processed image.
    """
    text = pytesseract.image_to_string(processed_image)
    return text


def estimate_image_quality(processed_image):
    """
    Estimate whether the image may be blurry using variance of Laplacian.
    Lower score usually means a blurrier image.
    """
    blur_score = cv2.Laplacian(processed_image, cv2.CV_64F).var()

    if blur_score < 50:
        return "Low", blur_score, "Image may be blurry. OCR results may be unreliable."
    elif blur_score < 120:
        return "Medium", blur_score, "Image quality is acceptable but may need manual review."
    else:
        return "High", blur_score, "Image appears clear."