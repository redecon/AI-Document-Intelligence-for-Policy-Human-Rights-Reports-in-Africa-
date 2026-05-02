import os
import csv
import pdfplumber
from langdetect import detect, detect_langs
import fasttext

FASTTEXT_MODEL_PATH = "lid.176.bin"  # download from fastText site if not already
ft_model = fasttext.load_model(FASTTEXT_MODEL_PATH)

pdf_files = [
    "docs\2013-E.C-Audit-finding-information.pdf",
    "docs\A_HRC_51_46-EN.pdf",
    "docs\A_HRC_51_46-FR.pdf",
    "docs\Audit Report - 2023.pdf",
    "docs\CBE_Annual_Report_2008_9.pdf",
    "docs\Ethiopia RPRF-11032024.pdf",
    "docs\Ethiopia.pdf",
    "docs\fta_performance_survey_final_report_2022.pdf",
    "docs\tax_expenditure_ethiopia_2021_22.pdf"
   
  
]

def extract_text(pdf_path, max_chars=1000):
    """Extract up to max_chars of text from a PDF using pdfplumber."""
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            if len(text) >= max_chars:
                break
            page_text = page.extract_text() or ""
            text += page_text
    return text[:max_chars]

def analyze_language(text):
    """Run langdetect and fastText on given text and return predictions."""
    # Langdetect
    try:
        lang_pred = detect(text)
        lang_conf = str(detect_langs(text))
    except Exception as e:
        lang_pred, lang_conf = "error", str(e)

    # FastText
    ft_pred = ft_model.predict(text.replace("\n", " "), k=3)
    labels = [lbl.replace("__label__", "") for lbl in ft_pred[0]]
    scores = ft_pred[1]

    return lang_pred, lang_conf, labels, scores

def main():
    # Prepare CSV output
    with open("language_predictions.csv", "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "filename", "langdetect_pred", "langdetect_conf",
            "fasttext_top1", "fasttext_score1",
            "fasttext_top2", "fasttext_score2",
            "fasttext_top3", "fasttext_score3"
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for pdf in pdf_files:
            if os.path.exists(pdf):
                text = extract_text(pdf)
                if text.strip():
                    lang_pred, lang_conf, labels, scores = analyze_language(text)
                    writer.writerow({
                        "filename": os.path.basename(pdf),
                        "langdetect_pred": lang_pred,
                        "langdetect_conf": lang_conf,
                        "fasttext_top1": labels[0],
                        "fasttext_score1": f"{scores[0]:.4f}",
                        "fasttext_top2": labels[1],
                        "fasttext_score2": f"{scores[1]:.4f}",
                        "fasttext_top3": labels[2],
                        "fasttext_score3": f"{scores[2]:.4f}",
                    })
                else:
                    writer.writerow({"filename": os.path.basename(pdf), "langdetect_pred": "no text"})
            else:
                writer.writerow({"filename": os.path.basename(pdf), "langdetect_pred": "file not found"})

if __name__ == "__main__":
    main()
