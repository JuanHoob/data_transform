#!/usr/bin/env python3
# scripts/tratamiento_datos/json_to_dual_pdf.py
# -*- coding: utf-8 -*-
"""
JSON DI -> Dual PDF (texto reconstruido + página original con resaltados)
Requisitos:
  pip install pymupdf

Uso (PowerShell):
  python scripts/tratamiento_datos/json_to_dual_pdf.py --json ".\\data\\limpios_json\\AirTAC-Booklet-EU-EN.json" ^
      --pdf ".\\data\\brutos_pdf\\AirTAC-Booklet-EU-EN.pdf" ^
      --out ".\\exports\\pdf\\AirTAC-Booklet-dual.pdf" ^
      --title "AirTAC Booklet - Dual (texto + original)"
"""
import os, json, argparse, textwrap
from typing import List, Dict, Any, Optional

import fitz  # PyMuPDF

def clean_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("-\n", "").replace("\r", "")
    s = s.replace(" oC", " °C").replace("u", "µ")
    return "\n".join(x.strip() for x in s.splitlines() if x.strip())

def spans_to_text(full: str, spans: List[Dict[str, Any]]) -> str:
    parts = []
    for sp in spans or []:
        off = sp.get("offset", 0); ln = sp.get("length", 0)
        parts.append(full[off:off+ln])
    return "".join(parts)

def table_to_tsv(table: Dict[str, Any], full: str) -> str:
    cells = table.get("cells", [])
    if not cells:
        return clean_text(spans_to_text(full, table.get("spans", [])))
    by_row: Dict[int, Dict[int, str]] = {}
    max_col = 0
    for c in cells:
        r = int(c.get("rowIndex", 0)); k = int(c.get("columnIndex", 0))
        max_col = max(max_col, k)
        val = c.get("content") or spans_to_text(full, c.get("spans", []))
        by_row.setdefault(r, {})[k] = (val or "").replace("\t", " ").strip()
    lines = []
    for r in sorted(by_row):
        row = [by_row[r].get(k, "") for k in range(0, max_col+1)]
        lines.append("\t".join(row))
    return "\n".join(lines)

def polygon_to_rect(polygon):
    if not polygon or len(polygon) < 8:
        return None
    xs = polygon[0::2]
    ys = polygon[1::2]
    return fitz.Rect(min(xs), min(ys), max(xs), max(ys))

def group_items_by_page(ar: Dict[str, Any]) -> Dict[int, List[Dict[str, Any]]]:
    full = ar.get("content", "")
    paras = ar.get("paragraphs", []) or []
    tables = ar.get("tables", []) or []
    out: Dict[int, List[Dict[str, Any]]] = {}

    def add_item(page_num: Optional[int], kind: str, section: str, content: str, poly):
        if page_num is None:
            return
        out.setdefault(page_num, []).append({
            "kind": kind,
            "section": section or "",
            "content": clean_text(content),
            "polygon": poly or []
        })

    for p in paras:
        page = None; poly = None
        for br in p.get("boundingRegions", []):
            page = br.get("pageNumber", page)
            if not poly and br.get("polygon"):
                poly = br["polygon"]
        txt = p.get("content") or spans_to_text(full, p.get("spans", []))
        add_item(page, "paragraph", p.get("heading","") or p.get("role","") or "", txt, poly)

    for t in tables:
        page = None; poly = None
        for br in t.get("boundingRegions", []):
            page = br.get("pageNumber", page)
            if not poly and br.get("polygon"):
                poly = br["polygon"]
        tsv = table_to_tsv(t, full)
        lines = [ln.split("\t") for ln in tsv.splitlines() if ln.strip()]
        md_table = ""
        if lines:
            header = "| " + " | ".join(lines[0]) + " |"
            sep =    "| " + " | ".join(["---"]*len(lines[0])) + " |"
            body = "\n".join("| " + " | ".join(r) + " |" for r in lines[1:])
            md_table = "\n".join([header, sep, body]) if body else "\n".join([header, sep])
        add_item(page, "table", t.get("caption","") or "", md_table or tsv, poly)

    if not out and ar.get("pages"):
        for pg in ar["pages"]:
            pnum = pg.get("pageNumber")
            for ln in pg.get("lines", []):
                txt = ln.get("content") or spans_to_text(full, ln.get("spans", []))
                add_item(pnum, "line", "", txt, None)

    for k in list(out.keys()):
        out[k] = [x for x in out[k] if x["content"]]
    return out

def main():
    parser = argparse.ArgumentParser(description="JSON DI -> Dual PDF (texto + página original con resaltados)")
    parser.add_argument("--json", required=True, help="Ruta al JSON de Document Intelligence")
    parser.add_argument("--pdf", required=True, help="Ruta al PDF original correspondiente")
    parser.add_argument("--out", required=True, help="Ruta del PDF de salida (p. ej., exports/pdf/loquesea.pdf)")
    parser.add_argument("--title", default="", help="Título opcional para portada")
    parser.add_argument("--font_size", type=float, default=9.5, help="Tamaño de fuente para el resumen")
    args = parser.parse_args()

    with open(args.json, "r", encoding="utf-8") as f:
        root = json.load(f)
    ar = root.get("analyzeResult", root)
    items_by_page = group_items_by_page(ar)
    if not items_by_page:
        raise SystemExit("No se encontraron elementos en el JSON (paragraphs/tables/lines).")

    src = fitz.open(args.pdf)
    dst = fitz.open()

    if args.title:
        page = dst.new_page(-1, width=595, height=842)
        page.insert_textbox(fitz.Rect(50, 200, 545, 800), args.title, fontsize=20, fontname="helv", align=1)
        page.insert_textbox(fitz.Rect(50, 260, 545, 800), f"Origen: {os.path.basename(args.pdf)}", fontsize=10, fontname="helv", align=1)

    for pnum in sorted(items_by_page.keys()):
        src_index = pnum - 1
        if src_index < 0 or src_index >= len(src):
            continue

        # Resumen
        page = dst.new_page(-1, width=595, height=842)
        page.insert_textbox(fitz.Rect(40, 30, 555, 60), f"Resumen reconstruido — p.{pnum}", fontsize=12, fontname="helv")
        y = 70
        for it in items_by_page[pnum]:
            block_header = f"[{it['kind'].upper()}] {it['section']}".strip()
            page.insert_textbox(fitz.Rect(40, y, 555, 820), block_header, fontsize=10, fontname="helv")
            y += 14
            used = page.insert_textbox(fitz.Rect(40, y, 555, 820), it["content"], fontsize=args.font_size, fontname="cour")
            y += max(24, used + 8)
            if y > 780:
                page = dst.new_page(-1, width=595, height=842)
                y = 40

        # Original + resaltados
        dst.insert_pdf(src, from_page=src_index, to_page=src_index)
        orig = dst[-1]
        for it in items_by_page[pnum]:
            rect = polygon_to_rect(it.get("polygon"))
            if rect is None:
                continue
            try:
                annot = orig.add_rect_annot(rect)
                annot.set_colors(stroke=(1,0,0), fill=(1,0,0))
                annot.set_opacity(0.15)
                annot.update()
            except Exception:
                pass
        try:
            orig.insert_textbox(fitz.Rect(30, 20, 565, 50), f"Página original — p.{pnum} (resaltados = zonas referenciadas)", fontsize=10, fontname="helv")
        except Exception:
            pass

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    dst.save(args.out)
    dst.close(); src.close()
    print(f"Listo -> {os.path.abspath(args.out)}")

if __name__ == "__main__":
    main()
