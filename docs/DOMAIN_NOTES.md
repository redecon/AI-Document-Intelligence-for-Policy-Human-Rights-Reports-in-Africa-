## Extraction Strategy Decision Tree
flowchart TD
    A["Start: Input PDF"] --> B{"Digital?"}
    B -->|Yes| C{"Simple Layout?"}
    C -->|Yes| D["FastText + pdfplumber"]
    C -->|No| E["Layout-aware Parser (Docling/Marker-PDF)"]
    B -->|"No (Scanned)"| F["OCR Preprocessing (OCRmyPDF)"]
    F --> G["Layout-aware Parser"]
    D --> H{"Confidence < Threshold?"}
    E --> H
    G --> H
    H -->|Yes| I["VLM-assisted Refinement (Gemini/vision models)"]
    H -->|No| J["Structured Output → Refinery"]

![alt text](flowchart.png)


## Failure Modes Across Civic Document Types
# PDF Extraction Failure Analysis Report

The following table documents specific failure modes encountered during the processing of various Ethiopian institutional and audit reports. These failures highlight the need for a robust, multi-stage extraction pipeline.

| Document Name | Page(s) | Failure Mode | Description | Suggested Mitigation |
| :--- | :--- | :--- | :--- | :--- |
| **Audit Report – 2023.pdf** | 2–95 | Structure Collapse | All pages except page 1 flagged as scanned (`is_scanned_guess=True`), yielding zero extracted text. | Apply OCR preprocessing (OCRmyPDF, Tesseract) before language detection. |
| **Audit Report – 2023.pdf** | 3–7 | Context Poverty | Language detection confidence dropped (FastText 0.44 for en), suggesting noisy or partial extraction. | Clean text by removing headers/footers; chunk semantically with captions. |
| **CBE Annual Report 2008–09.pdf** | All | Structure Collapse | Extraction returned “no text”; scanned layout defeated pdfplumber. | Use OCR pipeline; integrate layout-aware parsing for multi-column reports. |
| **Ethiopia RPRF-11032024.pdf** | 15 | Provenance Blindness | Extracted figures lacked bounding box linkage; no way to confirm placement in original tables. | Preserve provenance metadata (bbox, cell IDs) during extraction. |
| **fta_performance_survey_final_report_2022.pdf** | 22 | Context Poverty | Table of financial indicators followed by explanatory footnote; naive chunking risks separation. | Bind tables with adjacent notes/footnotes in semantic chunking. |
| **tax_expenditure_ethiopia_2021_22.pdf** | 16–21 | Provenance Blindness | Multiple pages with tables but no automatic linkage to source cells; verification requires manual check. | Add provenance metadata; structured schema with bounding boxes. |
| **World Report 2025 – Ethiopia.pdf** | 1–6 | Structure Collapse | Multi-column human rights report; risk of merged columns scrambling narrative. | Use layout-aware parsing (Docling, Marker-PDF LLM mode) to preserve column integrity. |



## Tool Architecture Observations
**MinerU:** Integrated pipeline (OCR, table recognition, markdown output) is powerful but heavy; backend requires Rust builds and ML models. Produces middle_json that can be adapted into custom schemas.

**Docling:** Strong at layout detection and provenance (bounding boxes, semantic objects). Better at preserving tables and figures than pdfplumber.

**Marker-PDF:** LLM mode (Gemini Flash) improves table fidelity and fixes OCR errors, but adds latency. Baseline mode is faster but flattens structure.

**Design Implication:** Refinery should normalize outputs from multiple tools into a unified schema, preserving provenance and layout fidelity while allowing fallback to lighter tools for simple digital PDFs.

## Multilingual & Low-Quality Scan Analysis
**Amharic Test:** FastText correctly identified am with high confidence; langdetect confused Amharic with Arabic (ar).

**Low-Quality Scan Flagging:** Pages with char_count=0 and is_scanned_guess=True (e.g., Audit Report 2023) reliably indicate OCR requirement.

**Implication:** Language detection must be paired with scan detection. FastText is robust for multilingual civic documents, but OCR preprocessing is mandatory for scanned audits.

## Pipeline Diagram
![alt text](pipeline.png)


## Real-World Observations
**Structure Collapse:** Scanned and multi‑column civic documents collapse under naive extraction, requiring OCR and layout‑aware parsing.

**Context Poverty:** Tables and figures lose meaning when detached from explanatory notes or captions. Semantic chunking is essential.

**Provenance Blindness:** Without bounding boxes or source cell IDs, extracted numbers cannot be traced back to their origin, undermining auditability.

**Multilingual Robustness:** FastText outperforms langdetect for Amharic and other non‑Latin scripts, but confidence thresholds must be enforced.

**Pipeline Readiness:** A five‑stage Refinery pipeline (ingest → preprocess → extract → normalize → analyze) ensures resilience across civic document types.

**Key Theme:** Document intelligence for civic audits and reports demands OCR integration, layout awareness, semantic binding, and provenance metadata. These are not optional features — they are prerequisites for trustworthy analysis in field deployments.