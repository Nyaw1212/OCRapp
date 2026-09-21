# Leave Card OCR Extractor

A local, read-only proof of concept for extracting text from scanned leave cards. It is deliberately separate from Leave Calendar and does not connect to Google Sheets, databases, MAGCLIP, or employee records.

## What Phase 1 does

- Opens one local PDF or image (`PDF`, `PNG`, `JPG/JPEG`, `BMP`, `TIFF/TIF`).
- Renders PDF pages locally and lets you move between them.
- Displays the original page with zoom and scrollbars.
- Runs Tesseract locally and displays raw text for review.
- Copies raw text to the clipboard only when you choose **Copy Raw Text**.

It never changes, renames, saves over, uploads, or exports the selected source file. There is no database, automatic record creation, or Leave Calendar integration.

## Setup on Windows

1. Install Python 3.11 or newer.
2. Install [Tesseract OCR for Windows](https://github.com/UB-Mannheim/tesseract/wiki). During setup, leave the default install location enabled.
3. In PowerShell, from this repository:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python app.py
   ```

If Tesseract is installed somewhere other than the usual Windows location, set `TESSERACT_CMD` before starting the app:

```powershell
$env:TESSERACT_CMD = 'D:\Apps\Tesseract-OCR\tesseract.exe'
python app.py
```

## Next phases

Phase 2 adds adjustable history and VL/SL crops. Phase 3 identifies candidate rows and always marks uncertain values for human review. Phase 4 produces a copy-only TSV compatible with Leave Calendar's **Paste Leave History Data** parser. No phase will write back to Leave Calendar.
