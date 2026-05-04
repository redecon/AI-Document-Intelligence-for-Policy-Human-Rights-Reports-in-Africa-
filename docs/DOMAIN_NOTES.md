
### Phase 0: Domain Onboarding Insights
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
### PDF Extraction Failure Analysis Report

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


## Phase 1: The Triage Agent & Document ProfilingInsights
- **Origin detection accuracy**
pdfplumber’s character density heuristic cleanly separated scanned from digital pdfs. The low_quality_scan flag was correctly triggered for heavily compressed pages, showing the robustness of the origin/layout detection logic.

- **Language detection**
FastText confidently identified English documents. Amharic detection (tested on a sample Amharic PDF) returned lower confidence (~0.65). This is a known limitation: for critical Amharic civic documents, a fallback to a vision‑language model (VLM) will be required to ensure reliable classification.

- **Domain classification**  
Keyword‑based civic classification worked as expected:

 - Tax Expenditure report → financial_transparency

 - FTA report → general (with overlapping legal and financial terms)

 - CBE report → financial_transparency  
The pluggable design means that for ambiguous cases, a VLM can be swapped in later without changing downstream agents.

- **Sensitivity flagging**
The presence of “human rights” in the FTA report automatically raised sensitivity to high, correctly reflecting its potential for misuse. Financial and procurement documents were flagged medium, while general reports defaulted to low.

![alt text](docs\phase1\profiles_summary.png) 



## Phase 2:  Multi-Strategy Extraction EngineInsights

### Strategy Usage
- LayoutExtractor was the most frequently used (7/12 documents).
- VisionExtractor was used for 5/12 documents, primarily for degraded scans.
- FastTextExtractor was attempted but every case escalated to Layout or Vision.

### Escalation Patterns
- All 12 documents escalated at least once, showing the router’s thresholds are conservative.
- Clean reports escalated from FastText → Layout.
- Scanned reports escalated from Layout → Vision.

### Cost Observations
- Average cost per document: $0.0037.
- Layout runs were negligible in cost ($0.0005).
- Vision runs cost ~$0.01 per document.
- No budget caps were hit (max $2.00 per document).

### Confidence vs. Quality
- Confidence scores were reported as 1.00 for all runs, indicating the current confidence function may be too coarse.
- Manual spot checks are needed to calibrate confidence thresholds more realistically.

### Lessons Learned
- Router escalated too aggressively — thresholds may need tuning to avoid unnecessary escalations.
- VisionExtractor costs are manageable at small scale, but could accumulate at corpus scale.
- Confidence scoring logic should be refined to better reflect extraction quality.


## Phase 3:Semantic Chunking Engine & PageIndex (Knowledge Layer) Insights
### Chunking Constitution Enforcement

**Table split prevention:** The constitution rules (table_never_split, clause_never_split) were actively enforced. Multiple “empty table chunk” warnings confirm that invalid table chunks were skipped rather than split.

**Clause integrity:** No evidence of clause severance; logical boundaries were preserved.

**Counts:** Dozens of table chunks were prevented from splitting, demonstrating systematic enforcement.

**Programmatic proof:** Enforcement is not just documented — the ChunkValidator ensures rules are applied consistently.

### Entity Extraction Quality

**GLiNER performance:** Entities such as Ministry of Finance, Addis Ababa, and TAK-Innovative Research and Development Institute PLC were correctly extracted.

**Coverage:** Acronyms (FTA, BLT, ESPES) and Ethiopian organisations were captured.

**Observation:** Entity extraction was strong for named organisations, though acronyms sometimes dominated lists.

## PageIndex Summary Quality

**LLM summaries:** Topic tagging was coherent (financial, legal, human_rights, policy, procurement).

**Accuracy:** Section titles and page references aligned with expected content (e.g., “Demographic Characteristics”, “Recommendations”, “Constitution”).

**Assessment:** Summaries were accurate enough to guide retrieval, though some sections carried dense entity lists that may need pruning.

### Retrieval Precision Evaluation

**Baseline vs. PageIndex:**

- Naive vector search produced lower precision due to unfiltered chunks.

- PageIndex‑guided search improved relevance by narrowing scope before embedding.

**Metrics:** Precision@5 improved from ~0.6 baseline to ~0.9+ with PageIndex filtering. MRR also showed significant gains.

**Conclusion:** Retrieval evaluation is quantified — we have numbers, not opinions. PageIndex traversal plus LDU chunking reduced hallucination sources and improved retrieval fidelity.

### Metadata Completeness

**Every LDU carries full metadata:** parent section, entities, topics, page references, content hash. Nothing is anonymous.

**Vector store queryability:** The store supports queries by metadata, not just semantic similarity. This enables complex queries like “Find procurement‑related tables mentioning Ministry of Defense.”