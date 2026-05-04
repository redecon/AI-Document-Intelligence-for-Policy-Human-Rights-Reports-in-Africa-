import os
import glob
import argparse
import pickle
import sqlite3
from collections import Counter

from src.tools.fact_table import FactTableBuilder
from src.models.document import ExtractedDocument


def build_fact_table():
    builder = FactTableBuilder()
    facts_total = []
    facts_per_doc = {}

    # Loop over all extracted documents
    for path in glob.glob(".refinery/extractions/*.pkl"):
        with open(path, "rb") as f:
            extracted_doc: ExtractedDocument = pickle.load(f)

        facts = builder.build(extracted_doc)
        facts_total.extend(facts)
        doc_label = getattr(extracted_doc, "doc_name", extracted_doc.document_id)
        facts_per_doc[doc_label] = len(facts)
        print(f"Processed {doc_label}: {len(facts)} facts")


    # Summary
    print("\n=== FactTable Summary ===")
    print(f"Total facts: {len(facts_total)}")
    for doc, count in facts_per_doc.items():
        print(f"{doc}: {count} facts")

    # Most common fact types
    fact_types = Counter([f.fact_type for f in facts_total])
    print("\nMost common fact types:")
    for ft, count in fact_types.most_common():
        print(f"{ft}: {count}")


def run_query(sql: str):
    conn = sqlite3.connect(".refinery/fact_table.db")
    cur = conn.cursor()
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        for row in rows:
            print(dict(zip(cols, row)))
    except Exception as e:
        print(f"Query failed: {e}")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Build and query FactTable")
    parser.add_argument("--query", type=str, help="Run an arbitrary SQL query against FactTable")
    args = parser.parse_args()

    if args.query:
        run_query(args.query)
    else:
        build_fact_table()
        # Demo query: budget facts for 2024
        print("\n=== Demo Query: Budget facts for 2024 ===")
        run_query("SELECT * FROM facts WHERE fact_type='budget' AND year=2024 LIMIT 5")


if __name__ == "__main__":
    main()


