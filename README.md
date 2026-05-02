## Setup & Usage
### 1. Environment Setup
Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
.\.venv\Scripts\activate    # Windows
```
Install dependencies:

```bash
pip install -r requirements.txt
```
Your requirements.txt should include:

pdfplumber
pytesseract
pillow
pyyaml
fasttext
pytest

**Note:** The Tesseract OCR engine  must also be installed (not just the Python wrapper):

- Windows: Install from UB Mannheim builds (github.com in Bing).

- macOS: brew install tesseract

- Ubuntu/Debian: sudo apt-get install tesseract-ocr


## 2. Phase 0 – Language Detection Script
In Phase 0 we used a simple script to benchmark language detection on PDFs.

Run:

```bash
python src/tools/language_detector.py
```
This will:

- Extract text from sample PDFs in docs/.

- Run both langdetect and FastText (lid.176.bin).

- Save predictions to language_predictions.csv.

### 3. Phase 1 – Triage Agent
The triage agent integrates origin/layout detection, language detection, civic classification, and profile serialization.

Run tests to validate:

```bash
pytest -q
```
You should see all tests pass (..... green dots). Tests cover:

- Origin detection (digital vs scanned).

- Language detection (English, Amharic, French).

- Civic classification (financial, human rights).

- Sensitivity levels.

- Profile JSON persistence.

## 4. Batch Profiling
Generate profiles for all PDFs in data/corpus/:

```bash
python -m scripts.batch_triage
```
This will:

- Loop over all PDFs.

- Call TriageAgent.profile() for each.

- Save individual JSON profiles in .refinery/profiles/.

- Produce a consolidated summary CSV:
.refinery/profiles/profiles_summary.csv

The summary includes:

- Document IDs
- Origin type
- Layout complexity  
- Primary language
- Domain hint
- Sensitivity
- Page count