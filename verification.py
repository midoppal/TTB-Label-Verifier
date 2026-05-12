import re
from rapidfuzz import fuzz


STANDARD_GOV_WARNING = (
    "GOVERNMENT WARNING: "
    "(1) ACCORDING TO THE SURGEON GENERAL, WOMEN SHOULD NOT DRINK "
    "ALCOHOLIC BEVERAGES DURING PREGNANCY BECAUSE OF THE RISK OF "
    "BIRTH DEFECTS. (2) CONSUMPTION OF ALCOHOLIC BEVERAGES IMPAIRS "
    "YOUR ABILITY TO DRIVE A CAR OR OPERATE MACHINERY, AND MAY CAUSE "
    "HEALTH PROBLEMS."
)


def normalize_text(text):
    if not text:
        return ""

    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text

def get_text_lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def best_line_match(expected, text):

    lines = get_text_lines(text)

    best_score = 0
    best_line = ""

    expected_norm = normalize_text(expected)

    for line in lines:
        line_norm = normalize_text(line)
        score = fuzz.ratio(expected_norm, line_norm)

        if score > best_score:
            best_score = score
            best_line = line

    return best_line, best_score

def fuzzy_compare(expected, detected, threshold=85):

    expected_norm = normalize_text(expected)
    detected_norm = normalize_text(detected)

    if not expected_norm:
        return "Not Provided", 0

    if not detected_norm:
        return "Not Found", 0

    score = fuzz.partial_ratio(expected_norm, detected_norm)

    if score >= threshold:
        return "Match", score
    elif score >= 65:
        return "Review", score
    else:
        return "Mismatch", score


def extract_abv(text):
  
    patterns = [
        r"(\d{1,2}(?:\.\d+)?)\s*%\s*(?:alc\.?/vol\.?|abv|alcohol)",
        r"alcohol\s*(?:by\s*volume)?\s*(\d{1,2}(?:\.\d+)?)\s*%",
        r"alc\.?\s*(\d{1,2}(?:\.\d+)?)\s*%"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1) + "%"

    return ""


def extract_net_contents(text):

    pattern = r"(\d+(?:\.\d+)?)\s*(ml|mL|ML|l|L|liter|liters)"
    match = re.search(pattern, text)

    if match:
        return match.group(1) + " " + match.group(2)

    return ""


def check_government_warning(text):

    raw_text = text
    normalized_label = normalize_text(text)
    normalized_warning = normalize_text(STANDARD_GOV_WARNING)

    prefix_present = "GOVERNMENT WARNING:" in raw_text
    prefix_case_issue = "Government Warning:" in raw_text or "government warning:" in raw_text

    warning_score = fuzz.partial_ratio(normalized_warning, normalized_label)

    if prefix_present and warning_score >= 85:
        return {
            "detected": "Government warning detected",
            "status": "Match",
            "score": warning_score,
            "notes": "Standard warning text appears to be present."
        }

    if prefix_case_issue:
        return {
            "detected": "Government warning detected with possible casing issue",
            "status": "Review",
            "score": warning_score,
            "notes": "Warning appears present, but prefix may not be fully uppercase."
        }

    if warning_score >= 70:
        return {
            "detected": "Possible government warning detected",
            "status": "Review",
            "score": warning_score,
            "notes": "Warning text appears partially present but may be incomplete or altered."
        }

    return {
        "detected": "Not found",
        "status": "Mismatch",
        "score": warning_score,
        "notes": "Required government warning was not confidently detected."
    }


def verify_label(ocr_text, expected_fields):

    results = []

  
    expected_brand = expected_fields.get("brand_name", "")
    detected_brand, brand_score = best_line_match(expected_brand, ocr_text)

    if not expected_brand:
        brand_status = "Not Provided"
    elif brand_score >= 85:
        brand_status = "Match"
    elif brand_score >= 65:
        brand_status = "Review"
    else:
        brand_status = "Mismatch"

    results.append({
        "Field": "Brand Name",
        "Expected": expected_brand,
        "Detected": detected_brand if detected_brand else "Not found",
        "Status": brand_status,
        "Confidence / Score": brand_score,
        "Notes": "Compared expected brand name against the closest OCR text line."
    })

   
    expected_class = expected_fields.get("class_type", "")
    detected_class, class_score = best_line_match(expected_class, ocr_text)

    if not expected_class:
        class_status = "Not Provided"
    elif class_score >= 80:
        class_status = "Match"
    elif class_score >= 60:
        class_status = "Review"
    else:
        class_status = "Mismatch"

    results.append({
        "Field": "Class / Type",
        "Expected": expected_class,
        "Detected": detected_class if detected_class else "Not found",
        "Status": class_status,
        "Confidence / Score": class_score,
        "Notes": "Compared expected class/type against the closest OCR text line."
    })

    
    detected_abv = extract_abv(ocr_text)
    abv_status, abv_score = fuzzy_compare(
        expected_fields.get("abv", ""),
        detected_abv,
        threshold=85
    )

    results.append({
        "Field": "Alcohol Content",
        "Expected": expected_fields.get("abv", ""),
        "Detected": detected_abv,
        "Status": abv_status,
        "Confidence / Score": abv_score,
        "Notes": "Extracted using ABV regex patterns."
    })

 
    detected_volume = extract_net_contents(ocr_text)
    volume_status, volume_score = fuzzy_compare(
        expected_fields.get("net_contents", ""),
        detected_volume,
        threshold=85
    )

    results.append({
        "Field": "Net Contents",
        "Expected": expected_fields.get("net_contents", ""),
        "Detected": detected_volume,
        "Status": volume_status,
        "Confidence / Score": volume_score,
        "Notes": "Extracted using volume regex patterns."
    })

    
    warning_result = check_government_warning(ocr_text)

    results.append({
        "Field": "Government Warning",
        "Expected": "Standard government health warning",
        "Detected": warning_result["detected"],
        "Status": warning_result["status"],
        "Confidence / Score": warning_result["score"],
        "Notes": warning_result["notes"]
    })

    return results