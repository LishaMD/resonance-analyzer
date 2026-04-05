# Text Extraction API

A Flask API that extracts text from various file formats including PDFs, Office documents, and images.

## Supported Formats

- **PDF** - via pdfplumber
- **DOCX** - via python-docx
- **PPTX** - via python-pptx
- **XLSX** - via openpyxl
- **Images (PNG, JPG, JPEG)** - via Tesseract OCR

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install Tesseract OCR (for image text extraction):
   - **macOS**: `brew install tesseract`
   - **Ubuntu/Debian**: `sudo apt-get install tesseract-ocr`
   - **Windows**: Download from https://github.com/UB-Mannheim/tesseract/wiki

## Running the API

```bash
python app.py
```

The API will start on `http://localhost:5000`

## API Endpoints

### POST /extract

Extracts text from multiple files provided as URLs.

**Request Body:**
```json
{
  "files": [
    {
      "url": "https://example.com/document.pdf",
      "filename": "document.pdf"
    },
    {
      "url": "https://example.com/image.png",
      "filename": "image.png"
    }
  ]
}
```

**Response:**
```json
{
  "files": [
    {
      "filename": "document.pdf",
      "extracted_text": "This is the extracted text..."
    },
    {
      "filename": "image.png",
      "error": "Failed to download file: 404 Not Found"
    }
  ]
}
```

### GET /

Health check endpoint that returns API status and supported formats.

## Example Usage

```bash
curl -X POST http://localhost:5000/extract \
  -H "Content-Type: application/json" \
  -d '{
    "files": [
      {
        "url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
        "filename": "dummy.pdf"
      }
    ]
  }'
```

## Error Handling

- Each file is processed independently
- If one file fails, others will still be processed
- Failed files return an `error` field instead of `extracted_text`
- The API returns 200 OK even if some files fail (check individual file results)
- Returns 400 Bad Request for malformed requests
- Returns 500 Internal Server Error for unexpected server errors

## Notes

- Files are downloaded to temporary storage and automatically cleaned up
- 30-second timeout for file downloads
- Tesseract OCR quality depends on image clarity and resolution
