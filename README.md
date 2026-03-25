# recipe_book

## Streamlit Community Cloud OCR Setup

To use image-based recipe import on Streamlit Community Cloud, install both Python and system dependencies.

### Python dependencies

These are already listed in `requirements.txt`:

- `Pillow`
- `pytesseract`

### System dependencies

Streamlit Community Cloud installs apt packages from `packages.txt`.
This repo includes:

- `tesseract-ocr`
- `tesseract-ocr-eng`

After pushing these files to GitHub and redeploying, OCR should work in the deployed app.

## Optional OCR.space API (Recommended for Handwriting)

The app supports OCR.space as a first-pass OCR provider, with automatic fallback to local Tesseract.

### Why use it

- Better handwriting OCR than local Tesseract in many cases
- Easier behavior across local and cloud environments

### Configure API key

Set `OCR_SPACE_API_KEY` either as:

- Local environment variable, or
- Streamlit Community Cloud secret

Example Streamlit secret:

```toml
OCR_SPACE_API_KEY = "your_api_key_here"
```

If no API key is present, or OCR.space fails to return usable text, the app falls back to local Tesseract OCR.