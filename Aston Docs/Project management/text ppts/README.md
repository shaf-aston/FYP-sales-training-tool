```markdown
# PDF Text and Visual Extractor

Extracts text and visual content (diagrams, images) from PDF files, converting images to readable text using OCR.

## Features

- **Text Extraction**: Extracts all text content from PDF files
- **Visual Extraction**: Extracts images and diagrams from PDFs
- **OCR Processing**: Converts images to readable text using Tesseract OCR
- **Flexible**: Automatically processes all PDF files in the parent directory (or a specified directory)
- **Rerunnable**: Can be executed multiple times without issues
- **No Hardcoding**: Dynamically finds and processes all PDFs

## Usage

Run the script from the `text ppts` directory or run it from anywhere with the `--dir` option:

```bash
python pdf_text_extractor.py
```

The script will:
1. Scan the parent directory (`Project management`) for all PDF files (or the provided `--dir`)
2. Extract text and images from each PDF
3. Perform OCR on all extracted images
4. Save results in an `extracted_content` folder next to the scanned directory

### Examples

1) Scan the parent directory (default):

   ```bash
   python pdf_text_extractor.py
   ```

2) Scan a specific folder recursively and set OCR language:

   ```bash
   python pdf_text_extractor.py --dir "C:/path/to/folder" --recursive --ocr-lang eng
   ```

3) If Tesseract is not on PATH (Windows), pass the tesseract executable path:

   ```bash
   python pdf_text_extractor.py --tesseract-cmd "C:/Program Files/Tesseract-OCR/tesseract.exe"
   ```

## Output

- **Text Files**: Each PDF generates a `[filename]_extracted.txt` file containing:
  - All text content from the PDF
  - OCR text from all images/diagrams
- **Images**: The script does not save images by default (it performs OCR in-memory), but the output text contains image metadata and OCR text.

## Technical Details

- Uses PyMuPDF (fitz) for PDF parsing and image extraction
- Uses Pillow for image processing
- Uses pytesseract for OCR text recognition
- Supports recursive scanning with `--recursive` and configurable OCR language via `--ocr-lang`
- Existing output files will be overwritten when running the script again

## Requirements

- Python 3.7+
- PyMuPDF (fitz)
- Pillow (PIL)
- pytesseract
- Tesseract OCR (system installation)

## Troubleshooting

- **OCR quality issues**: Depends on image quality in PDFs - poor quality images may produce inaccurate OCR results. Consider pre-processing images or using higher DPI sources.
- **Large PDFs**: May take significant time to process due to image extraction and OCR; consider running on a machine with more CPU cores or splitting PDFs.
- **No images found**: Some PDFs may not contain extractable images (they may be embedded differently or be pure scanned pages).
- **Text extraction errors**: May occur with scanned PDFs or complex layouts; OCR handles scanned images but layout parsing may be imperfect.
- **Permission errors**: Ensure write access to the output directory

## Notes

- Install Python dependencies from `requirements.txt`.
- Install the Tesseract OCR engine separately — the Python package `pytesseract` is a wrapper and requires the Tesseract binary.
- On Windows, Tesseract is commonly installed to `C:/Program Files/Tesseract-OCR/tesseract.exe` (the script will auto-detect this path if present).

```
# PDF Text and Visual Extractor

Extracts text and visual content (diagrams, images) from PDF files, converting images to readable text using OCR.

## Features

- **Text Extraction**: Extracts all text content from PDF files
- **Visual Extraction**: Extracts images and diagrams from PDFs
- **OCR Processing**: Converts images to readable text using Tesseract OCR
- **Flexible**: Automatically processes all PDF files in the parent directory
- **Rerunnable**: Can be executed multiple times without issues
- **No Hardcoding**: Dynamically finds and processes all PDFs

## Usage

Run the script from the `text ppts` directory:

```bash
python pdf_text_extractor.py
```

The script will:
1. Scan the parent directory (`Project management`) for all PDF files
2. Extract text and images from each PDF
3. Perform OCR on all extracted images
4. Save results in an `extracted_content` folder in the parent directory

## Output

- **Text Files**: Each PDF generates a `[filename]_extracted.txt` file containing:
  - All text content from the PDF
  - OCR text from all images/diagrams
- **Images**: All extracted images are saved as separate files for reference

## Technical Details

- Uses PyMuPDF (fitz) for PDF parsing and image extraction
- Uses Pillow for image processing
- Uses pytesseract for OCR text recognition
- Processes only direct child PDF files in the parent directory
- Existing output files will be overwritten when running the script again

## Requirements

- Python 3.7+
- PyMuPDF (fitz)
- Pillow (PIL)
- pytesseract
- Tesseract OCR (system installation)

## Troubleshooting

- **OCR quality issues**: Depends on image quality in PDFs - poor quality images may produce inaccurate OCR results
- **Large PDFs**: May take significant time to process due to image extraction and OCR
- **No images found**: Some PDFs may not contain extractable images
- **Text extraction errors**: May occur with scanned PDFs or complex layouts
- **Permission errors**: Ensure write access to the output directory
