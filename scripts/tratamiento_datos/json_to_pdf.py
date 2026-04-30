# scripts/tratamiento_de_datos/json_to_pdf.py
"""
Convierte un JSON de Azure Document Intelligence a un PDF de **solo texto** (flujo lineal).
Uso ejemplo:
python scripts/tratamiento_datos/json_to_pdf.py ^
  --json ".\\data\\limpios_json\\AirTAC-Booklet-EU-EN.json" ^
  --out  ".\\exports\\pdf\\AirTAC-Booklet-EU-EN.text.pdf" ^
  --title "AirTAC Booklet - Texto extraído" ^
  --font Helvetica ^
  --fontsize 9 ^
  --margin 36

Requisitos:
pip install reportlab
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any


def ensure_pdf_dependencies() -> tuple[Any, Any, Any, Any, Any]:
    """Carga ReportLab bajo demanda para permitir imports sin el extra pdf."""
    try:
        from reportlab.lib.pagesizes import A4, LETTER
        from reportlab.lib.utils import simpleSplit
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError(
            "Missing PDF dependencies. Install with: pip install -e '.[pdf]'"
        ) from exc
    return canvas, A4, LETTER, simpleSplit, (pdfmetrics, TTFont)


def _unwrap_analyze_result(data: dict[str, Any]) -> dict[str, Any]:
    if "analyzeResult" in data and isinstance(data["analyzeResult"], dict):
        return data["analyzeResult"]
    return data


def _collect_paragraphs_by_page(di: dict[str, Any]) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    paragraphs = di.get("paragraphs") or []
    if not isinstance(paragraphs, list):
        return out
    for p in paragraphs:
        content = p.get("content")
        if not content or not isinstance(content, str):
            continue
        regions = p.get("boundingRegions") or []
        page_num = None
        for r in regions:
            if isinstance(r, dict) and isinstance(r.get("pageNumber"), int):
                page_num = r["pageNumber"]
                break
        if page_num is None:
            page_num = 1
        out.setdefault(page_num, []).append(content.strip())
    return out


def _collect_lines_by_page(di: dict[str, Any]) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    pages = di.get("pages") or []
    if not isinstance(pages, list):
        return out
    for page in pages:
        pn = page.get("pageNumber")
        if not isinstance(pn, int):
            continue
        lines = page.get("lines") or []
        bucket: list[str] = out.setdefault(pn, [])
        for ln in lines:
            content = None
            if isinstance(ln, dict):
                content = ln.get("content") or ln.get("text")
            elif isinstance(ln, str):
                content = ln
            if content:
                bucket.append(str(content).strip())
    return out


def extract_pages_text(data: dict[str, Any]) -> list[list[str]]:
    di = _unwrap_analyze_result(data)
    by_page = _collect_paragraphs_by_page(di) or _collect_lines_by_page(di)
    if not by_page:
        content = di.get("content")
        if isinstance(content, str) and content.strip():
            return [[p.strip() for p in content.split("\n\n") if p.strip()]]
        raise ValueError("No se han encontrado 'paragraphs', 'lines' ni 'content' en el JSON.")
    max_page = max(by_page.keys())
    return [by_page.get(p, []) for p in range(1, max_page + 1)]


def _register_ttf_if_provided(ttf_path: str | None, font_name: str) -> str:
    _, _, _, _, pdf_tools = ensure_pdf_dependencies()
    pdfmetrics, tt_font = pdf_tools
    if ttf_path:
        if not os.path.isfile(ttf_path):
            raise FileNotFoundError(f"Archivo TTF no encontrado: {ttf_path}")
        pdfmetrics.registerFont(tt_font(font_name, ttf_path))
    return font_name


def _wrap_paragraph_to_lines(
    text: str, font_name: str, font_size: float, max_width: float
) -> list[str]:
    _, _, _, simple_split, _ = ensure_pdf_dependencies()
    return simple_split(text, font_name, font_size, max_width)


def render_text_flow(
    pages_text: list[list[str]],
    out_pdf: str,
    title: str | None = None,
    font_name: str = "Helvetica",
    font_size: float = 9.0,
    margin: float = 36.0,
    pagesize_name: str = "A4",
    ttf_path: str | None = None,
    leading_factor: float = 1.25,
) -> None:
    canvas_module, a4, letter, _, _ = ensure_pdf_dependencies()
    page_size_map = {"A4": a4, "LETTER": letter}
    page_size = page_size_map.get(pagesize_name.upper(), a4)
    width, height = page_size
    font_name = _register_ttf_if_provided(ttf_path, font_name)
    c = canvas_module.Canvas(out_pdf, pagesize=page_size)

    left = margin
    right = width - margin
    top = height - margin
    bottom = margin
    usable_width = right - left
    leading = font_size * leading_factor
    x = left
    y = top

    c.setFont(font_name, font_size)
    if title:
        title_font = min(font_size * 1.4, font_size + 4)
        c.setFont(font_name, title_font)
        for tl in _wrap_paragraph_to_lines(title, font_name, title_font, usable_width):
            if y - leading < bottom:
                c.showPage()
                c.setFont(font_name, title_font)
                y = top
            c.drawString(x, y, tl)
            y -= leading
        y -= leading * 0.6
        c.setFont(font_name, font_size)

    for p_index, paragraphs in enumerate(pages_text, start=1):
        if p_index > 1:
            c.showPage()
            c.setFont(font_name, font_size)
            y = top
        for para in paragraphs:
            if not para:
                continue
            for line in _wrap_paragraph_to_lines(para, font_name, font_size, usable_width):
                if y - leading < bottom:
                    c.showPage()
                    c.setFont(font_name, font_size)
                    y = top
                c.drawString(x, y, line)
                y -= leading
            y -= leading * 0.35
    c.save()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DI JSON -> PDF de texto (flujo lineal)")
    p.add_argument("--json", required=True, help="Ruta al archivo JSON de Azure DI.")
    p.add_argument(
        "--out", required=True, help="Ruta de salida del PDF (p. ej., exports/pdf/loquesea.pdf)."
    )
    p.add_argument("--title", default=None, help="Título opcional.")
    p.add_argument("--font", default="Helvetica", help="Fuente Type1 o alias para TTF.")
    p.add_argument("--ttf", default=None, help="Ruta a un .ttf (Unicode extendido).")
    p.add_argument("--fontsize", type=float, default=9.0, help="Tamaño de fuente.")
    p.add_argument("--margin", type=float, default=36.0, help="Margen (pt).")
    p.add_argument("--pagesize", choices=["A4", "LETTER"], default="A4", help="Tamaño de página.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    src = os.path.abspath(args.json)
    dst = os.path.abspath(args.out)
    if not os.path.isfile(src):
        print(f"[json_to_pdf] No existe el JSON: {src}")
        return 1
    dst_dir = os.path.dirname(dst)
    if not os.path.isdir(dst_dir):
        print(f"[json_to_pdf] La carpeta de salida no existe: {dst_dir}")
        return 1
    try:
        with open(src, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[json_to_pdf] JSON inválido ({src}): {e}")
        return 1
    try:
        pages_text = extract_pages_text(data)
    except Exception as e:
        print(f"[json_to_pdf] Error extrayendo texto del DI: {e}")
        return 1
    try:
        render_text_flow(
            pages_text=pages_text,
            out_pdf=dst,
            title=args.title,
            font_name=args.font,
            font_size=float(args.fontsize or 9.0),
            margin=float(args.margin or 36.0),
            pagesize_name=args.pagesize,
            ttf_path=args.ttf,
        )
    except Exception as e:
        print(f"[json_to_pdf] Error renderizando PDF: {e}")
        return 1
    print(f"[json_to_pdf] OK → {dst}  (páginas DI: {len(pages_text)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
