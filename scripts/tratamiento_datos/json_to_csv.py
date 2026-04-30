#!/usr/bin/env python3
# scripts/tratamiento_datos/json_to_csv.py
# Convierte JSON de Azure Document Intelligence a CSV (párrafos, tablas, líneas).
# Uso:
#   python scripts/tratamiento_datos/json_to_csv.py --input ".\\data\\limpios_json\\*.json"
#   python scripts/tratamiento_datos/json_to_csv.py --input input.json --out exports/csv/out.csv
# Salida columnas: file, doc_title, page, block_type, role, section, content

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
from typing import Any


def text_from_spans(full: str, spans: list[dict[str, Any]]) -> str:
    parts = []
    for sp in spans or []:
        offset = sp.get("offset", 0)
        length = sp.get("length", 0)
        parts.append(full[offset : offset + length])
    return "".join(parts).strip()


def table_to_tsv(tbl: dict[str, Any], full: str) -> str:
    cells = tbl.get("cells", [])
    if not cells:
        return text_from_spans(full, tbl.get("spans", [])) or ""
    rows: dict[int, dict[int, str]] = {}
    max_col = 0
    for cell in cells:
        row_index = cell.get("rowIndex", 0)
        column_index = cell.get("columnIndex", 0)
        max_col = max(max_col, column_index)
        value = cell.get("content") or text_from_spans(full, cell.get("spans", []))
        rows.setdefault(row_index, {})[column_index] = (value or "").replace("\t", " ").strip()
    lines = []
    for row_index in sorted(rows):
        line = [rows[row_index].get(column_index, "") for column_index in range(0, max_col + 1)]
        lines.append("\t".join(line))
    return "\n".join(lines)


def clean_text(value: str) -> str:
    if not value:
        return ""
    value = value.replace("-\n", "").replace("\r", "")
    return "\n".join(line.strip() for line in value.splitlines() if line.strip())


def extract_rows(obj: dict[str, Any], filename: str) -> list[dict[str, Any]]:
    # Soporta esquemas de DI con analyzeResult o content/pages/paragraphs
    ar = obj.get("analyzeResult", obj)
    full = ar.get("content", "")
    paras = ar.get("paragraphs", []) or []
    tables = ar.get("tables", []) or []
    out = []

    # Párrafos
    for p in paras:
        page = None
        for br in p.get("boundingRegions", []):
            page = br.get("pageNumber", page)
        role = p.get("role") or p.get("kind") or ""
        section = p.get("heading", "")
        txt = p.get("content") or text_from_spans(full, p.get("spans", []))
        txt = clean_text(txt)
        if not txt:
            continue
        out.append(
            {
                "file": os.path.basename(filename),
                "doc_title": os.path.splitext(os.path.basename(filename))[0],
                "page": page,
                "block_type": "paragraph",
                "role": role,
                "section": section,
                "content": txt,
            }
        )

    # Tablas
    for t in tables:
        page = None
        for br in t.get("boundingRegions", []):
            page = br.get("pageNumber", page)
        txt = clean_text(table_to_tsv(t, full))
        if not txt:
            continue
        out.append(
            {
                "file": os.path.basename(filename),
                "doc_title": os.path.splitext(os.path.basename(filename))[0],
                "page": page,
                "block_type": "table",
                "role": "",
                "section": t.get("caption", "") or "",
                "content": txt,
            }
        )

    # Fallback a líneas si no hay paragraphs/tables
    if not out and ar.get("pages"):
        for p in ar["pages"]:
            page_num = p.get("pageNumber")
            for ln in p.get("lines", []):
                txt = ln.get("content") or text_from_spans(full, ln.get("spans", []))
                txt = clean_text(txt)
                if not txt:
                    continue
                out.append(
                    {
                        "file": os.path.basename(filename),
                        "doc_title": os.path.splitext(os.path.basename(filename))[0],
                        "page": page_num,
                        "block_type": "line",
                        "role": "",
                        "section": "",
                        "content": txt,
                    }
                )
    return out


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="DI JSON -> CSV")
    ap.add_argument(
        "--input", required=True, help="Ruta .json o patrón (ej.: data/limpios_json/*.json)"
    )
    ap.add_argument(
        "--out",
        default="exports/csv/export_di.csv",
        help="CSV de salida (por defecto: exports/csv/export_di.csv)",
    )
    ap.add_argument("--min_chars", type=int, default=25, help="Mínimo de caracteres por fila")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    files = glob.glob(args.input)
    if not files:
        print("Sin archivos para procesar.")
        return 1

    all_rows = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            obj = json.load(fh)
        for r in extract_rows(obj, f):
            if len(r["content"]) >= args.min_chars:
                all_rows.append(r)

    cols = ["file", "doc_title", "page", "block_type", "role", "section", "content"]
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="") as fo:
        w = csv.DictWriter(fo, fieldnames=cols)
        w.writeheader()
        w.writerows(all_rows)

    print(f"OK: {len(all_rows)} filas -> {os.path.abspath(args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
