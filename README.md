# AI-Powered Alcohol Label Verification App

## Overview

This prototype helps alcohol-label compliance agents verify whether label artwork matches submitted application fields. The app extracts text from an uploaded label image and compares the detected information against expected application values.

The project focuses on repetitive checks such as brand name, class/type, alcohol content, net contents, and the required government health warning statement.

## Features

- Upload alcohol label image
- Extract text using OCR
- Verify brand name
- Verify class/type designation
- Verify alcohol content / ABV
- Verify net contents
- Check for government warning statement
- Flag matches, mismatches, and uncertain results
- Display OCR text for manual review
- Show estimated image quality
- Show processing time
- Download verification report as CSV

## Tech Stack

- Python
- Streamlit
- Tesseract OCR
- OpenCV
- Pillow
- RapidFuzz
- Pandas

## How It Works

1. The user enters expected application values.
2. The user uploads an alcohol label image.
3. The app preprocesses the image using grayscale conversion, denoising, and adaptive thresholding.
4. OCR extracts text from the processed image.
5. The app compares detected text against expected values using regex and fuzzy matching.
6. The app returns a verification report with statuses such as Match, Review, Mismatch, or Not Found.

## Setup Instructions

Install Python dependencies:

```bash
pip install -r requirements.txt