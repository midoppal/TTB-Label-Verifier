import streamlit as st
import pandas as pd
from ocr_utils import preprocess_image, extract_text_from_image, estimate_image_quality
from verification import verify_label
import time

st.set_page_config(
    page_title="AI Alcohol Label Verification",
    page_icon="🍾",
    layout="wide"
)

# def highlight_status(row):
#     status = row["Status"]

#     if status == "Match":
#         return ["background-color: #d4edda"] * len(row)
#     elif status == "Review":
#         return ["background-color: #fff3cd"] * len(row)
#     elif status in ["Mismatch", "Not Found"]:
#         return ["background-color: #f8d7da"] * len(row)
#     else:
#         return [""] * len(row)
    
st.title("AI-Powered Alcohol Label Verification App")

st.write(
    """
    Upload an alcohol label image and enter the expected application values.
    The app extracts label text using OCR and checks whether key compliance fields match.
    """
)


with st.sidebar:
    st.header("Expected Application Fields")

    brand_name = st.text_input("Brand Name", value="OLD TOM DISTILLERY")
    class_type = st.text_input("Class / Type", value="Kentucky Straight Bourbon Whiskey")
    abv = st.text_input("Alcohol Content / ABV", value="45%")
    net_contents = st.text_input("Net Contents", value="750 mL")

    st.caption(
        "These values represent the information from the submitted label application."
    )


uploaded_files = st.file_uploader(
    "Upload one or more label images",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True
)


st.markdown("### Step 1: Enter expected application values")
st.markdown("### Step 2: Upload label image")
st.markdown("### Step 3: Review verification results")

expected_fields = {
        "brand_name": brand_name,
        "class_type": class_type,
        "abv": abv,
        "net_contents": net_contents
    }

if uploaded_files:
    all_results = []

    for uploaded_file in uploaded_files:
        with st.spinner(f"Processing {uploaded_file.name}..."):
            start_time = time.time()

            original_image, processed_image = preprocess_image(uploaded_file)
            quality_label, quality_score, quality_note = estimate_image_quality(processed_image)

            ocr_text = extract_text_from_image(processed_image)
            results = verify_label(ocr_text, expected_fields)

            elapsed_time = time.time() - start_time

            for row in results:
                row["File"] = uploaded_file.name
                row["Image Quality"] = quality_label
                row["Blur Score"] = round(quality_score, 2)
                row["Processing Time (sec)"] = round(elapsed_time, 2)
                all_results.append(row)

    results_df = pd.DataFrame(all_results)


    preferred_column_order = [
        "File",
        "Field",
        "Expected",
        "Detected",
        "Status",
        "Confidence / Score",
        "Image Quality",
        "Blur Score",
        "Processing Time (sec)",
        "Notes"
    ]

    results_df = results_df[preferred_column_order]

    field_order = {
        "Brand Name": 1,
        "Class / Type": 2,
        "Alcohol Content": 3,
        "Net Contents": 4,
        "Government Warning": 5
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
            mismatches = status_counts.get("Mismatch", 0)
            not_found = status_counts.get("Not Found", 0)

            col1, col2, col3, col4 = st.columns(4)

            col1.metric("Matches", matches)
            col2.metric("Needs Review", reviews)
            col3.metric("Mismatches", mismatches)
            col4.metric("Not Found", not_found)

            display_df = file_df.drop(columns=["File"])

            st.dataframe(
                display_df,
                use_container_width=True
            )

    st.subheader("Accumulated Batch Report")

    # st.dataframe(
    #     results_df,
    #     use_container_width=True
    # )
    
    st.dataframe(
        display_df.style.apply(highlight_status, axis=1),
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