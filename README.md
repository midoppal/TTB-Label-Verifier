# AI-Powered Alcohol Label Verification App

## Overview

This project is a Streamlit prototype for alcohol label compliance review. It helps a reviewer compare text extracted from label artwork against the expected values from a label application.

The app focuses on the high-volume checks described in the take-home prompt: brand name, class/type designation, alcohol content, net contents, producer/importer information, country of origin for imported products, additional disclosures, and the mandatory government health warning statement.

The goal is not to replace a trained TTB reviewer. The goal is to reduce routine visual matching work, surface likely mismatches quickly, and provide a simple workflow that a compliance agent can use without technical training.

## Deployed Application

Add the deployed Streamlit URL here before submitting:

```text
https://ttb-label-verifier.streamlit.app
```

## Repository

Source code repository:

```text
https://github.com/midoppal/TTB-Label-Verifier
```

## Key Features

- Upload one or more label images in PNG, JPG, JPEG, or PDF format
- Render PDF label submissions page by page for OCR and review
- Extract label text using Tesseract OCR
- Compare extracted text against expected application fields
- Verify common label fields:
  - Brand name
  - Class/type designation
  - Alcohol content / ABV
  - Net contents
  - Name and address of bottler, producer, importer, or similar responsible party
  - Country of origin when the product is marked as imported
  - Additional expected disclosures or claims
  - Government health warning statement
- Apply simplified requirement profiles by beverage type:
  - Distilled spirits
  - Wine
  - Malt beverage / beer
- Account for selected regulatory context, including imported products, lower-ABV wine, and malt beverages with alcohol from added flavors or other added nonbeverage ingredients
- Use fuzzy matching so harmless formatting differences can be flagged for review instead of automatically treated as failures
- Estimate image quality using a blur score
- Display processing time for each uploaded file
- Display raw OCR text for each file to support manual review
- Show a side-by-side label preview with highlighted extracted text
- Show per-file review results and an accumulated batch report
- Export the full batch report as a CSV

## Why This Approach

The stakeholder notes emphasized that reviewers spend significant time on repetitive matching tasks. This prototype therefore uses OCR plus deterministic comparison logic instead of a fully generative AI workflow.

That choice has a few advantages for this use case:

- It is fast enough for the expected workflow.
- It can run locally without depending on blocked outbound cloud API calls.
- It produces explainable results with match scores and reviewer notes.
- It keeps the reviewer in control for judgment-heavy or ambiguous cases.

The app uses fuzzy matching for fields such as brand name and class/type because the prompt specifically notes that labels may differ in capitalization or punctuation while still representing the same value. It uses stricter checks for structured values such as ABV and net contents, and it separately checks the government warning text and uppercase prefix.

## Tech Stack

- Python
- Streamlit
- Tesseract OCR
- pytesseract
- OpenCV
- Pillow
- RapidFuzz
- Pandas
- NumPy
- PyMuPDF

## Project Structure

```text
.
├── app.py              # Streamlit UI and batch processing workflow
├── ocr_utils.py        # Image/PDF loading, preprocessing, OCR, and image quality estimate
├── verification.py     # Field extraction, fuzzy matching, and compliance checks
├── requirements.txt    # Python dependencies
├── packages.txt        # System package for Streamlit Cloud deployment
└── .streamlit/
    └── config.toml     # Streamlit theme configuration
```

## Local Setup

### 1. Install Tesseract OCR

This app requires the Tesseract executable in addition to the Python package `pytesseract`.

On Windows, install Tesseract from the official installer or a package manager, then make sure the Tesseract executable is available on your PATH.

On macOS:

```bash
brew install tesseract
```

On Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
```

Windows PowerShell:

```bash
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
streamlit run app.py
```

The app will open in a browser, usually at:

```text
http://localhost:8501
```

## How To Use

1. Select the beverage type in the sidebar.
2. Mark whether the product is imported.
3. Enter the expected application values.
4. Upload one or more label images or PDFs.
5. Review the per-file results.
6. Use the accumulated batch report for the full upload set.
7. Download the CSV report if needed.

## Verification Logic

The verification layer combines field-specific extraction with fuzzy matching:

- Brand name and class/type are compared against the closest OCR text line.
- ABV is extracted with regular expressions for common alcohol-content formats.
- Net contents are extracted with regular expressions for common volume formats.
- Name/address is checked with fuzzy matching plus simple producer/importer/address heuristics.
- Country of origin is checked only when the imported-product option is enabled.
- Government warning is checked for the required uppercase prefix and approximate standard warning text.
- Additional disclosures are optional and checked only when the user provides expected disclosure text.
- PDF submissions are rendered page by page, then processed through the same OCR and verification workflow as image uploads.

Results use the following statuses:

- `Match`: the field was confidently found.
- `Review`: the field may match, but manual review is recommended.
- `Mismatch`: the expected field was not confidently found or does not match.
- `Not Found`: a structured value such as ABV or net contents could not be extracted.
- `Not Provided`: the reviewer did not enter an expected value.
- `Not Required`: the check was skipped based on the selected requirement profile.
- `Info`: informational notes about assumptions or skipped optional checks.

## Deployment Notes (If current URL doesn't work)

This project is ready to deploy on Streamlit Community Cloud.

Important deployment files:

- `requirements.txt` installs the Python dependencies.
- `packages.txt` installs the system package `tesseract-ocr`.
- `.streamlit/config.toml` sets the app theme.

To deploy:

1. Push the repository to GitHub.
2. Create a new Streamlit Community Cloud app.
3. Select this repository.
4. Set the main file path to `app.py`.
5. Deploy the app.
6. Paste the deployed URL into the `Deployed Application` section above.

## Assumptions

- Uploaded images contain readable label artwork.
- OCR output is good enough for text-level comparison.
- The app is a standalone prototype and does not integrate with COLA or any internal TTB system.
- The app does not store uploaded labels or application data.
- Requirement profiles are simplified and intended to demonstrate product thinking, not provide legal advice.
- A human reviewer remains responsible for final regulatory decisions.

## Limitations and Trade-Offs

- OCR can struggle with glare, low resolution, curved bottles, unusual fonts, and angled photos; would need stronger OCR model for better performance but comes with tradeoffs.
- The app checks text presence and approximate text matches; it does not reliably verify font size, boldness, placement, or label layout.
- The government warning check can identify missing or altered text, but OCR alone cannot fully confirm all formatting requirements.
- Beverage-specific label rules are simplified for the prototype.
- The system is optimized for explainable matching rather than broad legal analysis.
- No cloud AI API is used, which improves portability in restricted network environments but limits advanced image understanding.
- Batch handling can be done better with CSV input intergration for varying application fields, but would reduce easability.

## Possible Future Improvements

- Add confidence thresholds configurable by reviewer or beverage type. (May reduce easability, so I didn't include)
- Add image rotation and perspective correction for poorly photographed labels. (Not confident for reliability in testing yet)

## Evaluation Criteria Alignment

- Correctness and completeness: covers the core label fields described in the prompt and adds beverage/import context.
- Code quality and organization: separates UI, OCR utilities, and verification logic.
- Technical choices: uses local OCR and deterministic checks suitable for restricted government network environments.
- User experience: supports batch uploads, simple sidebar input, visible status categories, and downloadable reports.
- Error handling and reviewability: flags uncertain results for human review instead of making silent pass/fail decisions.
- Attention to requirements: includes processing time, batch handling, image-quality signal, and explicit prototype limitations.
