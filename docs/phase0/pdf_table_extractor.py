import pdfplumber

def extract_table_across_pages(pdf_path, start_page, end_page):
    """
    Extracts tables across multiple pages and stitches them together.
    
    Args:
        pdf_path (str): Path to the PDF file.
        start_page (int): Starting page number (1-based).
        end_page (int): Ending page number (inclusive, 1-based).
    
    Returns:
        list: Combined rows from tables across pages.
    """
    combined_rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num in range(start_page-1, end_page):  # pdfplumber is 0-based
            page = pdf.pages[page_num]
            tables = page.extract_tables()
            text = page.extract_text()

            print(f"\n=== Page {page_num+1} TEXT ===")
            print(text[:500])  # preview first 500 chars

            if tables:
                print(f"=== Page {page_num+1} TABLES ===")
                for t in tables:
                    for row in t:
                        print(row)
                        combined_rows.append(row)
            else:
                print(f"No tables detected on page {page_num+1}")

    return combined_rows


if __name__ == "__main__":
    pdf_path = "docs/tax_expenditure_ethiopia_2021_22.pdf"
    # Table spans pages 54–56, so stitch them
    stitched_table = extract_table_across_pages(pdf_path, start_page=54, end_page=56)

    print("\n=== STITCHED TABLE ===")
    for row in stitched_table:
        print(row)
