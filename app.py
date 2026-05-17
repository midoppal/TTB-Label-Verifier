import streamlit as st
import pandas as pd
import html
import re
from ocr_utils import (
    extract_text_from_image,
    estimate_image_quality,
    load_image,
    preprocess_pil_image,
    render_pdf_pages,
)
from verification import verify_label
import time

st.set_page_config(
    page_title="AI Alcohol Label Verification",
    page_icon="🍾",
    layout="wide"
)

BATCH_TEMPLATE_COLUMNS = [
    "file",
    "page",
    "beverage_type",
    "is_imported",
    "wine_abv_category",
    "malt_added_alcohol",
    "brand_name",
    "class_type",
    "abv",
    "net_contents",
    "producer_name_address",
    "country_of_origin",
    "additional_disclosures",
]

BATCH_TEMPLATE_ROW = {
    "file": "old_tom_label.png",
    "page": "",
    "beverage_type": "Distilled Spirits",
    "is_imported": "false",
    "wine_abv_category": "",
    "malt_added_alcohol": "false",
    "brand_name": "OLD TOM DISTILLERY",
    "class_type": "Kentucky Straight Bourbon Whiskey",
    "abv": "45%",
    "net_contents": "750 mL",
    "producer_name_address": "Bottled by Old Tom Distillery, Louisville, KY",
    "country_of_origin": "",
    "additional_disclosures": "",
}

COLUMN_ALIASES = {
    "file": ["file", "filename", "file_name", "label_file", "upload_file"],
    "page": ["page", "page_number", "pdf_page"],
    "beverage_type": ["beverage_type", "beverage", "product_type"],
    "is_imported": ["is_imported", "imported", "imported_product"],
    "wine_abv_category": ["wine_abv_category", "wine_category", "wine_abv"],
    "malt_added_alcohol": ["malt_added_alcohol", "added_alcohol", "malt_has_added_alcohol"],
    "brand_name": ["brand_name", "brand"],
    "class_type": ["class_type", "class", "type", "class_designation"],
    "abv": ["abv", "alcohol_content", "alcohol_content_abv"],
    "net_contents": ["net_contents", "net_content", "volume"],
    "producer_name_address": [
        "producer_name_address",
        "name_address",
        "name_and_address",
        "producer_address",
        "bottler_producer_importer",
    ],
    "country_of_origin": ["country_of_origin", "origin_country", "country"],
    "additional_disclosures": ["additional_disclosures", "disclosures", "claims"],
}


def normalize_column_name(column_name):
    return re.sub(r"[^a-z0-9]+", "_", str(column_name).strip().lower()).strip("_")


def normalize_file_key(file_name):
    normalized = str(file_name).strip().replace("\\", "/").split("/")[-1].lower()
    return re.sub(r"\s+", " ", normalized)


def clean_cell(value):
    if pd.isna(value):
        return ""

    return str(value).strip()


def normalize_page_value(value):
    page_value = clean_cell(value)

    if not page_value:
        return ""

    try:
        return str(int(float(page_value)))
    except ValueError:
        match = re.search(r"\d+", page_value)
        return match.group(0) if match else page_value


def parse_bool(value, default=False):
    value_text = clean_cell(value).lower()

    if not value_text:
        return default

    if value_text in {"true", "yes", "y", "1", "imported"}:
        return True

    if value_text in {"false", "no", "n", "0", "not imported"}:
        return False

    return default


def normalize_beverage_type(value, default):
    value_text = clean_cell(value)
    normalized = value_text.lower()

    if not value_text:
        return default

    if "spirit" in normalized or "distill" in normalized:
        return "Distilled Spirits"

    if "wine" in normalized:
        return "Wine"

    if "beer" in normalized or "malt" in normalized:
        return "Malt Beverage / Beer"

    return value_text


def find_manifest_column(columns, field_name):
    aliases = COLUMN_ALIASES.get(field_name, [field_name])

    for alias in aliases:
        normalized_alias = normalize_column_name(alias)

        if normalized_alias in columns:
            return normalized_alias

    return None


def build_expected_fields_from_row(row, columns, fallback_fields):
    expected = fallback_fields.copy()

    for field_name in BATCH_TEMPLATE_COLUMNS:
        if field_name in {"file", "page"}:
            continue

        column_name = find_manifest_column(columns, field_name)

        if not column_name:
            continue

        value = row.get(column_name, "")

        if field_name == "beverage_type":
            expected[field_name] = normalize_beverage_type(value, expected.get(field_name, "Distilled Spirits"))
        elif field_name in {"is_imported", "malt_added_alcohol"}:
            expected[field_name] = parse_bool(value, expected.get(field_name, False))
        else:
            expected[field_name] = clean_cell(value)

    return expected


def load_batch_manifest(batch_manifest_file, fallback_fields):
    if batch_manifest_file is None:
        return {}, []

    try:
        manifest_df = pd.read_csv(batch_manifest_file).fillna("")
    except Exception as error:
        return {}, [f"Could not read batch CSV: {error}"]

    manifest_df = manifest_df.rename(columns=normalize_column_name)
    columns = set(manifest_df.columns)
    file_column = find_manifest_column(columns, "file")
    page_column = find_manifest_column(columns, "page")
    errors = []
    manifest = {}

    if not file_column:
        return {}, ["Batch CSV must include a `file` column matching uploaded file names."]

    for row_number, row in manifest_df.iterrows():
        file_name = clean_cell(row.get(file_column, ""))

        if not file_name:
            errors.append(f"Batch CSV row {row_number + 2} has no file name and was skipped.")
            continue

        expected = build_expected_fields_from_row(row, columns, fallback_fields)
        page_number = normalize_page_value(row.get(page_column, "")) if page_column else ""
        manifest_label = file_name

        if page_number:
            manifest_label = f"{file_name} - page {page_number}"

        manifest[normalize_file_key(manifest_label)] = {
            "expected_fields": expected,
            "display_name": manifest_label,
        }

        if not page_number:
            manifest[normalize_file_key(file_name)] = {
                "expected_fields": expected,
                "display_name": file_name,
            }

    return manifest, errors


def get_expected_fields_for_upload(file_label, original_file_name, batch_manifest, fallback_fields):
    file_key = normalize_file_key(file_label)
    original_file_key = normalize_file_key(original_file_name)

    if file_key in batch_manifest:
        return batch_manifest[file_key]["expected_fields"], "Batch CSV", file_key

    if original_file_key in batch_manifest:
        return batch_manifest[original_file_key]["expected_fields"], "Batch CSV", original_file_key

    return fallback_fields, "Sidebar Defaults", None


def build_batch_template_csv():
    return pd.DataFrame([BATCH_TEMPLATE_ROW], columns=BATCH_TEMPLATE_COLUMNS).to_csv(index=False).encode("utf-8")


def highlight_status(row):
    status = row["Status"]

    if status == "Match":
        return ["background-color: #d4edda"] * len(row)
    elif status == "Review":
        return ["background-color: #fff3cd"] * len(row)
    elif status in ["Mismatch", "Not Found"]:
        return ["background-color: #f8d7da"] * len(row)
    elif status in ["Not Required", "Info"]:
        return ["background-color: #e2e3e5"] * len(row)
    else:
        return [""] * len(row)


def get_highlight_terms(file_df):
    ignored_detected_values = {
        "",
        "N/A",
        "Not found",
        "Skipped",
        "Government warning detected",
        "Government warning detected with possible casing issue",
        "Possible government warning detected",
        "Possible name/address statement detected",
    }

    terms = []

    for _, row in file_df.iterrows():
        detected_value = str(row.get("Detected", "")).strip()
        field_name = str(row.get("Field", "")).strip()

        if detected_value and detected_value not in ignored_detected_values:
            terms.append(detected_value)

        if field_name == "Government Warning" and detected_value != "Not found":
            terms.append("GOVERNMENT WARNING")

    unique_terms = {}

    for term in terms:
        normalized = term.lower()

        if len(term) >= 3 and normalized not in unique_terms:
            unique_terms[normalized] = term

    return sorted(unique_terms.values(), key=len, reverse=True)


def render_highlighted_ocr_text(ocr_text, file_df):
    if not ocr_text.strip():
        highlighted_text = html.escape("No OCR text detected.")
    else:
        terms = get_highlight_terms(file_df)

        if terms:
            pattern = re.compile(
                "|".join(re.escape(term) for term in terms),
                re.IGNORECASE
            )

            highlighted_parts = []
            last_index = 0

            for match in pattern.finditer(ocr_text):
                highlighted_parts.append(html.escape(ocr_text[last_index:match.start()]))
                highlighted_parts.append(
                    "<mark style='background: #fde68a; padding: 0 2px; border-radius: 3px;'>"
                    f"{html.escape(match.group(0))}"
                    "</mark>"
                )
                last_index = match.end()

            highlighted_parts.append(html.escape(ocr_text[last_index:]))
            highlighted_text = "".join(highlighted_parts)
        else:
            highlighted_text = html.escape(ocr_text)

    return (
        "<div style='border: 1px solid #e5e7eb; border-radius: 8px; "
        "padding: 12px; background: #f8fafc; max-height: 360px; overflow: auto;'>"
        "<pre style='white-space: pre-wrap; margin: 0; color: #111827; "
        "font-size: 0.9rem; line-height: 1.45;'>"
        f"{highlighted_text}"
        "</pre></div>"
    )


def get_label_pages(uploaded_file):
    """
    Return one or more PIL images to process from an uploaded image or PDF.
    PDFs are processed one page at a time and labeled clearly in batch output.
    """
    if uploaded_file.name.lower().endswith(".pdf"):
        return [
            (f"{uploaded_file.name} - page {page_number}", page_image)
            for page_number, page_image in render_pdf_pages(uploaded_file)
        ]

    return [(uploaded_file.name, load_image(uploaded_file))]


st.title("AI-Powered Alcohol Label Verification App")

st.write(
    """
    Upload an alcohol label image or PDF and enter the expected application values.
    The app extracts label text using OCR and checks whether key compliance fields match.
    """
)

st.info(
    """
    This prototype applies simplified requirement profiles based on beverage type and import status.
    It supports common checks from TTB label guidance but does not replace full regulatory review.
    """
)


with st.sidebar:
    st.header("Application Details")

    beverage_type = st.selectbox(
        "Beverage Type",
        ["Distilled Spirits", "Wine", "Malt Beverage / Beer"]
    )

    is_imported = st.checkbox("Imported product?", value=False)

    wine_abv_category = None
    malt_added_alcohol = False

    if beverage_type == "Wine":
        wine_abv_category = st.selectbox(
            "Wine ABV Category",
            ["7% or more ABV", "Less than 7% ABV"]
        )

    if beverage_type == "Malt Beverage / Beer":
        malt_added_alcohol = st.checkbox(
            "Contains alcohol from added flavors or other added nonbeverage ingredients?",
            value=False
        )

    st.divider()

    st.header("Expected Application Fields")

    brand_name = st.text_input("Brand Name", value="")
    class_type = st.text_input("Class / Type", value="")
    abv = st.text_input("Alcohol Content / ABV", value="")
    net_contents = st.text_input("Net Contents", value="")

    producer_name_address = st.text_area(
        "Name and Address of Bottler / Producer / Importer",
        value="",
        placeholder="Example: Bottled by ABC Distillery, Frederick, MD"
    )

    country_of_origin = ""

    if is_imported:
        country_of_origin = st.text_input(
            "Country of Origin",
            value="",
            placeholder="Example: Product of France"
        )

    st.caption(
        "Enter the expected values from the submitted label application."
    )
    additional_disclosures = st.text_area(
        "Additional Expected Disclosures or Claims",
        value="",
        placeholder="Example: Contains: sulfites; FD&C Yellow #5; age statement; state of distillation"
    )

    st.divider()

    st.header("Batch Application CSV")
    st.caption(
        "Optional: upload a CSV when different labels in the batch have different expected application values."
    )
    batch_manifest_file = st.file_uploader(
        "Expected fields CSV",
        type=["csv"],
        key="batch_manifest_csv"
    )
    st.download_button(
        label="Download CSV Template",
        data=build_batch_template_csv(),
        file_name="batch_expected_fields_template.csv",
        mime="text/csv"
    )


uploaded_files = st.file_uploader(
    "Upload one or more label images or PDFs",
    type=["png", "jpg", "jpeg", "pdf"],
    accept_multiple_files=True
)


st.markdown("### Step 1: Enter expected application values or upload a batch CSV")
st.markdown("### Step 2: Upload label image")
st.markdown("### Step 3: Review verification results")

expected_fields = {
    "beverage_type": beverage_type,
    "is_imported": is_imported,
    "wine_abv_category": wine_abv_category,
    "malt_added_alcohol": malt_added_alcohol,
    "brand_name": brand_name,
    "class_type": class_type,
    "abv": abv,
    "net_contents": net_contents,
    "producer_name_address": producer_name_address,
    "country_of_origin": country_of_origin,
    "additional_disclosures": additional_disclosures
}

batch_manifest, batch_manifest_errors = load_batch_manifest(batch_manifest_file, expected_fields)

for batch_error in batch_manifest_errors:
    st.warning(batch_error)

if batch_manifest:
    st.success(f"Loaded {len(batch_manifest)} batch application mapping(s) from CSV.")

if uploaded_files:
    all_results = []
    image_by_file = {}
    ocr_text_by_file = {}
    matched_batch_keys = set()

    for uploaded_file in uploaded_files:
        with st.spinner(f"Processing {uploaded_file.name}..."):
            try:
                label_pages = get_label_pages(uploaded_file)
            except Exception as error:
                st.error(f"Could not process {uploaded_file.name}: {error}")
                continue

            for file_label, label_image in label_pages:
                start_time = time.time()

                original_image, processed_image = preprocess_pil_image(label_image)
                image_by_file[file_label] = original_image
                quality_label, quality_score, quality_note = estimate_image_quality(processed_image)

                ocr_text = extract_text_from_image(processed_image)
                ocr_text_by_file[file_label] = ocr_text
                file_expected_fields, application_source, matched_batch_key = get_expected_fields_for_upload(
                    file_label,
                    uploaded_file.name,
                    batch_manifest,
                    expected_fields
                )

                if matched_batch_key:
                    matched_batch_keys.add(matched_batch_key)

                results = verify_label(ocr_text, file_expected_fields)

                elapsed_time = time.time() - start_time

                for row in results:
                    row["File"] = file_label
                    row["Application Source"] = application_source
                    row["Image Quality"] = quality_label
                    row["Blur Score"] = round(quality_score, 2)
                    row["Processing Time (sec)"] = round(elapsed_time, 2)
                    all_results.append(row)

    if batch_manifest:
        unmatched_batch_rows = [
            item["display_name"]
            for key, item in batch_manifest.items()
            if key not in matched_batch_keys
        ]

        if unmatched_batch_rows:
            unmatched_preview = ", ".join(sorted(set(unmatched_batch_rows))[:5])
            st.warning(
                "Some batch CSV rows did not match uploaded files/pages: "
                f"{unmatched_preview}"
            )

    if not all_results:
        st.warning("No readable label files were processed.")
        st.stop()

    results_df = pd.DataFrame(all_results)

    # Put File first so the accumulated table is easier to read
    preferred_column_order = [
        "File",
        "Field",
        "Expected",
        "Detected",
        "Status",
        "Confidence / Score",
        "Application Source",
        "Image Quality",
        "Blur Score",
        "Processing Time (sec)",
        "Notes"
    ]

    results_df = results_df[preferred_column_order]

    # Sort by file, then by a meaningful field order
    field_order = {
        "Brand Name": 1,
        "Class / Type": 2,
        "Alcohol Content": 3,
        "Net Contents": 4,
        "Name and Address": 5,
        "Country of Origin": 6,
        "Additional Disclosures": 7,
        "Government Warning": 8,
        "Requirement Profile Note": 9
    }

    results_df["Field Sort Order"] = results_df["Field"].map(field_order).fillna(99)

    results_df = results_df.sort_values(
        by=["File", "Field Sort Order"]
    ).drop(columns=["Field Sort Order"])

    st.subheader("Per-File Verification Results")

    for file_name, file_df in results_df.groupby("File"):
        with st.expander(f"Results for {file_name}", expanded=True):
            status_counts = file_df["Status"].value_counts().to_dict()

            matches = status_counts.get("Match", 0)
            reviews = status_counts.get("Review", 0)
            mismatches = status_counts.get("Mismatch", 0) + status_counts.get("Not Found", 0)
            not_provided = status_counts.get("Not Provided", 0)
            not_required = status_counts.get("Not Required", 0)

            col1, col2, col3, col4, col5 = st.columns(5)

            col1.metric("Matches", matches)
            col2.metric("Needs Review", reviews)
            col3.metric("Mismatches", mismatches)
            col4.metric("Missing Input", not_provided)
            col5.metric("Not Required", not_required)

            display_df = file_df.drop(columns=["File"])

            st.dataframe(
                display_df,
                use_container_width=True
            )

            preview_col, ocr_col = st.columns(2)

            with preview_col:
                st.markdown("**Label Preview**")
                st.image(
                    image_by_file.get(file_name),
                    use_container_width=True
                )

            with ocr_col:
                st.markdown("**Extracted Text**")
                st.markdown(
                    render_highlighted_ocr_text(
                        ocr_text_by_file.get(file_name, ""),
                        file_df
                    ),
                    unsafe_allow_html=True
                )

    st.subheader("Accumulated Batch Report")

    st.dataframe(
        results_df.style.apply(highlight_status, axis=1),
        use_container_width=True
    )

    csv = results_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Download Full Batch Report as CSV",
        data=csv,
        file_name="batch_label_verification_report.csv",
        mime="text/csv"
    )

else:
    st.info("Upload a label image to begin.")
