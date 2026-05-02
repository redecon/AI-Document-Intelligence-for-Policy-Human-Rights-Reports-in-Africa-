import os
import pdfplumber
import fitz 
import pandas as pd

def analyze_pdf(file_path):
    results = []
    filename = os.path.basename(file_path)

    # Use PyMuPDF for page count (robust)
    doc = fitz.open(file_path)
    total_pages = doc.page_count
    print(f"Processing: {filename} | Pages: {total_pages}")

    # Use pdfplumber for text + tables
    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            char_count = len(text)

            # Heuristic: very low text density → scanned/image-only
            is_scanned_guess = char_count < 50

            # Table detection
            tables = page.find_tables()
            table_count = len(tables)

            results.append({
                "filename": filename,
                "page": page_num,
                "char_count": char_count,
                "table_count": table_count,
                "is_scanned_guess": is_scanned_guess
            })

    return results


def analyze_folder(folder_path, output_csv="summary.csv"):
    all_results = []
    for file in os.listdir(folder_path):
        if file.lower().endswith(".pdf"):
            file_path = os.path.join(folder_path, file)
            all_results.extend(analyze_pdf(file_path))

    df = pd.DataFrame(all_results)
    df.to_csv(output_csv, index=False)
    print(f"\nAnalysis complete. Results saved to {output_csv}")


if __name__ == "__main__":
    folder = "docs"
    analyze_folder(folder, output_csv="ethiopian_summary.csv")
