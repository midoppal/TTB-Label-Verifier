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

#########################################
# Requirements
#########################################

def get_requirement_profile(expected_fields):
    beverage_type = expected_fields.get("beverage_type", "Distilled Spirits")
    is_imported = expected_fields.get("is_imported", False)
    wine_abv_category = expected_fields.get("wine_abv_category")
    malt_added_alcohol = expected_fields.get("malt_added_alcohol", False)

    profile = {
        "brand_name": True,
        "class_type": True,
        "abv": True,
        "net_contents": True,
        "producer_name_address": True,
        "country_of_origin": is_imported,
        "government_warning": True,
        "notes": []
    }

    if beverage_type == "Distilled Spirits":
        profile["notes"].append(
            "Distilled spirits generally require brand name, alcohol content, and class/type designation."
        )

    elif beverage_type == "Wine":
        if wine_abv_category == "Less than 7% ABV":
            profile["notes"].append(
                "Wine under 7% ABV is treated as a special case. This prototype still checks common label fields, but full FDA food-labeling review is outside scope."
            )
        else:
            profile["notes"].append(
                "Wine at 7% or more ABV generally requires common TTB wine label fields."
            )

        profile["abv"] = True

    elif beverage_type == "Malt Beverage / Beer":
        if malt_added_alcohol:
            profile["abv"] = True
            profile["notes"].append(
                "For malt beverages, alcohol content is mandatory when alcohol comes from added flavors or other added nonbeverage ingredients."
            )
        else:
            profile["abv"] = False
            profile["notes"].append(
                "For malt beverages, alcohol content may be optional unless required by the product formulation or state law."
            )

    return profile


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

#########################################
# Address Checks
#########################################
def contains_address_like_text(text):
    text_norm = normalize_text(text)

    producer_phrases = [
        "bottled by",
        "produced by",
        "brewed by",
        "distilled by",
        "imported by",
        "packed by",
        "vinted by",
        "cellared by",
        "produced and bottled by",
        "imported and bottled by"
    ]

    has_producer_phrase = any(phrase in text_norm for phrase in producer_phrases)

    # simple city/state pattern
    has_city_state = bool(
        re.search(r"\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*,\s*[A-Z]{2}\b", text)
    )

    has_zip = bool(re.search(r"\b\d{5}(?:-\d{4})?\b", text))

    return has_producer_phrase and (has_city_state or has_zip)

#########################################
# Field Checks
#########################################
def check_expected_text_field(field_name, expected_value, ocr_text, threshold=80):
    detected_line, score = best_line_match(expected_value, ocr_text)

    if not expected_value:
        status = "Not Provided"
        notes = "No expected value was provided by the user."
    elif score >= threshold:
        status = "Match"
        notes = "Expected value closely matches OCR text."
    elif score >= 60:
        status = "Review"
        notes = "Possible match found, but manual review is recommended."
    else:
        status = "Mismatch"
        notes = "Expected value was not confidently found in the OCR text."

    return {
        "Field": field_name,
        "Expected": expected_value,
        "Detected": detected_line if detected_line else "Not found",
        "Status": status,
        "Confidence / Score": score,
        "Notes": notes
    }



def check_name_address(ocr_text, expected_value):
    base_result = check_expected_text_field(
        "Name and Address",
        expected_value,
        ocr_text,
        threshold=75
    )

    address_like = contains_address_like_text(ocr_text)

    if base_result["Status"] == "Mismatch" and address_like:
        base_result["Status"] = "Review"
        base_result["Notes"] = (
            "A producer/importer-style name/address statement appears to exist, "
            "but it does not closely match the expected value."
        )

    elif base_result["Status"] == "Not Provided" and address_like:
        base_result["Status"] = "Review"
        base_result["Detected"] = "Possible name/address statement detected"
        base_result["Notes"] = (
            "No expected value was provided, but the label appears to contain a producer/importer statement."
        )

    elif not address_like and base_result["Status"] in ["Mismatch", "Not Provided"]:
        base_result["Notes"] = (
            "No clear bottler, producer, brewer, distiller, or importer address statement was detected."
        )

    return base_result


#########################################
# Origin Checks
#########################################
def check_country_of_origin(ocr_text, expected_country):
    """
    Check country of origin for imported products.
    Looks for exact/fuzzy country text and common origin phrases.
    """
    if not expected_country:
        return {
            "Field": "Country of Origin",
            "Expected": "",
            "Detected": "Not found",
            "Status": "Not Provided",
            "Confidence / Score": 0,
            "Notes": "Imported product was selected, but no expected country of origin was provided."
        }

    origin_phrases = [
        f"product of {expected_country}",
        f"produced in {expected_country}",
        f"made in {expected_country}",
        f"imported from {expected_country}",
        expected_country
    ]

    best_score = 0
    best_phrase = ""

    for phrase in origin_phrases:
        score = fuzz.partial_ratio(
            normalize_text(phrase),
            normalize_text(ocr_text)
        )

        if score > best_score:
            best_score = score
            best_phrase = phrase

    if best_score >= 85:
        status = "Match"
        notes = "Country of origin was found or strongly matched in OCR text."
    elif best_score >= 65:
        status = "Review"
        notes = "Possible country-of-origin match found, but manual review is recommended."
    else:
        status = "Mismatch"
        notes = "Country of origin was not confidently detected."

    return {
        "Field": "Country of Origin",
        "Expected": expected_country,
        "Detected": best_phrase if best_score >= 65 else "Not found",
        "Status": status,
        "Confidence / Score": best_score,
        "Notes": notes
    }
    
    
#########################################
# Fuzzy Compare
#########################################
def fuzzy_compare(expected, detected, threshold=85):
    """
    Compare expected and detected strings.
    Returns status and score.
    """
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


#########################################
# Field Extraction
#########################################
def extract_abv(text):
    """
    Extract ABV-like values:
    Examples:
    - 45% Alc./Vol.
    - 45% ABV
    - ALC 45% BY VOL
    """
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
    """
    Extract bottle volume:
    Examples:
    - 750 mL
    - 1 L
    - 375 ML
    """
    pattern = r"(\d+(?:\.\d+)?)\s*(ml|mL|ML|l|L|liter|liters)"
    match = re.search(pattern, text)

    if match:
        return match.group(1) + " " + match.group(2)

    return ""


#########################################
# Warning Checks
#########################################
def check_government_warning(text):
    """
    Check whether government warning appears.
    For prototype, we check:
    - Is GOVERNMENT WARNING present?
    - Is the prefix uppercase?
    - Is the standard warning approximately present?
    """
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


#########################################
# Main Verification
#########################################
def verify_label(ocr_text, expected_fields):
    """
    Main verification function.
    Applies different checks based on beverage type and import status.
    """
    results = []
    profile = get_requirement_profile(expected_fields)

    if profile["brand_name"]:
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

    if profile["class_type"]:
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

    if profile["abv"]:
        detected_abv = extract_abv(ocr_text)
        abv_status, abv_score = fuzzy_compare(
            expected_fields.get("abv", ""),
            detected_abv,
            threshold=85
        )

        abv_notes = "Extracted using ABV regex patterns."

        if expected_fields.get("beverage_type") == "Wine":
            abv_notes += (
                " For wine, ABV rules can vary by alcohol level and designation; this prototype performs a text-level verification."
            )

        results.append({
            "Field": "Alcohol Content",
            "Expected": expected_fields.get("abv", ""),
            "Detected": detected_abv if detected_abv else "Not found",
            "Status": abv_status,
            "Confidence / Score": abv_score,
            "Notes": abv_notes
        })

    else:
        results.append({
            "Field": "Alcohol Content",
            "Expected": expected_fields.get("abv", ""),
            "Detected": "Skipped",
            "Status": "Not Required",
            "Confidence / Score": 0,
            "Notes": "This check was skipped based on the selected beverage-type profile."
        })

    if profile["net_contents"]:
        detected_volume = extract_net_contents(ocr_text)
        volume_status, volume_score = fuzzy_compare(
            expected_fields.get("net_contents", ""),
            detected_volume,
            threshold=85
        )

        results.append({
            "Field": "Net Contents",
            "Expected": expected_fields.get("net_contents", ""),
            "Detected": detected_volume if detected_volume else "Not found",
            "Status": volume_status,
            "Confidence / Score": volume_score,
            "Notes": "Extracted using volume regex patterns."
        })

   
    if profile["producer_name_address"]:
        results.append(
            check_name_address(
                ocr_text,
                expected_fields.get("producer_name_address", "")
            )
        )

   
    if profile["country_of_origin"]:
        results.append(
            check_country_of_origin(
                ocr_text,
                expected_fields.get("country_of_origin", "")
            )
        )
    else:
        results.append({
            "Field": "Country of Origin",
            "Expected": "",
            "Detected": "Skipped",
            "Status": "Not Required",
            "Confidence / Score": 0,
            "Notes": "Country of origin check is only enabled when imported product is selected."
        })
    
    additional_disclosures = expected_fields.get("additional_disclosures", "")

    if additional_disclosures:
        results.append(
            check_expected_text_field(
                "Additional Disclosures",
                additional_disclosures,
                ocr_text,
                threshold=70
            )
        )
    else:
        results.append({
            "Field": "Additional Disclosures",
            "Expected": "",
            "Detected": "Skipped",
            "Status": "Info",
            "Confidence / Score": 0,
            "Notes": "No additional expected disclosures were provided. Some disclosures are conditional based on ingredients, processing, or product claims."
        })

   
    if profile["government_warning"]:
        warning_result = check_government_warning(ocr_text)

        results.append({
            "Field": "Government Warning",
            "Expected": "Standard government health warning",
            "Detected": warning_result["detected"],
            "Status": warning_result["status"],
            "Confidence / Score": warning_result["score"],
            "Notes": warning_result["notes"]
        })

  
    for note in profile["notes"]:
        results.append({
            "Field": "Requirement Profile Note",
            "Expected": expected_fields.get("beverage_type", ""),
            "Detected": "N/A",
            "Status": "Info",
            "Confidence / Score": 0,
            "Notes": note
        })

    return results
