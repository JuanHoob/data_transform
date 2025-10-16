# scripts/csv_to_doc_md.py
import csv, os, argparse, itertools
ap=argparse.ArgumentParser(); ap.add_argument("--csv", required=True)
ap.add_argument("--outdir", default="exports/docs_md"); args=ap.parse_args()
os.makedirs(args.outdir, exist_ok=True)
with open(args.csv, encoding="utf-8") as f:
    rows=sorted(csv.DictReader(f), key=lambda r:(r["doc_title"], int(r["page"] or 0)))
for doc_title, group in itertools.groupby(rows, key=lambda r:r["doc_title"]):
    parts=[f"# {doc_title}\n"]
    for r in group:
        pg=r.get("page") or ""; bt=r.get("block_type") or ""; sec=r.get("section") or ""
        if sec: parts.append(f"\n## {sec} (p.{pg}) [{bt}]\n")
        else:   parts.append(f"\n### p.{pg} [{bt}]\n")
        parts.append((r.get("content") or "").strip()+"\n")
    name="".join(c if c.isalnum() or c in "-_." else "-" for c in doc_title) + ".md"
    open(os.path.join(args.outdir, name), "w", encoding="utf-8").write("".join(parts))
print("OK")
