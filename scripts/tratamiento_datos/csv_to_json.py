# scripts/tratamiento_datos/csv_to_json.py
import os, csv, json, argparse, re

ap = argparse.ArgumentParser(description="CSV -> NDJSON (para Azure AI Search u otros).")
ap.add_argument("--csv", required=True, help="Ruta al CSV (p. ej., exports/csv/export_di.csv)")
ap.add_argument("--out", default="exports/csv/export_azure.ndjson", help="Ruta NDJSON (por defecto: exports/csv/export_azure.ndjson)")
ap.add_argument("--index-name", default="invk-ocr-chunks", help="Nombre de índice (si aplica)")
args = ap.parse_args()

os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

def slug(s):
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", (s or "")).strip("-")[:64]

with open(args.csv, encoding="utf-8") as f, open(args.out, "w", encoding="utf-8") as o:
    r = csv.DictReader(f)
    for k, row in enumerate(r, start=1):
        doc = {
            "@search.action": "mergeOrUpload",
            "id": f"{slug(row.get('doc_title'))}-p{row.get('page','0')}-{k:06d}",
            "content": row.get("content", ""),
            "doc_title": row.get("doc_title", ""),
            "page": int(row.get("page") or 0),
            "block_type": row.get("block_type", ""),
            "role": row.get("role", ""),
            "section": row.get("section", ""),
            "source": "pdf",
            "lang": "es"
        }
        o.write(json.dumps(doc, ensure_ascii=False) + "\n")

print("OK")
