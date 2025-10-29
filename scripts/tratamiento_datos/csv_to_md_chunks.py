# scripts/tratamiento_datos/csv_to_md_chunks.py
import os, csv, argparse, textwrap

ap = argparse.ArgumentParser(description="CSV -> MD chunks (para RAG).")
ap.add_argument("--csv", required=True, help="Ruta al CSV (p. ej., exports/csv/export_di.csv)")
ap.add_argument("--outdir", default="exports/md_chunks", help="Carpeta de salida (por defecto: exports/md_chunks)")
ap.add_argument("--prefix", default="", help="Prefijo de nombre de archivo (opcional)")
args = ap.parse_args()

os.makedirs(args.outdir, exist_ok=True)

with open(args.csv, encoding="utf-8") as f:
    r = csv.DictReader(f)
    for i, row in enumerate(r, start=1):
        dt = row.get("doc_title", "")
        pg = row.get("page", "")
        bt = row.get("block_type", "")
        sec = row.get("section", "")
        txt = row.get("content", "").strip()
        body = f"# {dt} — p.{pg} [{bt}]\n"
        if sec:
            body += f"**{sec}**\n\n"
        body += textwrap.dedent(txt) + "\n"
        path = os.path.join(args.outdir, f"{args.prefix}{i:05d}.md")
        with open(path, "w", encoding="utf-8") as o:
            o.write(body)

print("OK")
