#!/usr/bin/env python3
"""Convierte un CSV de bloques DI a documentos Markdown por titulo."""

from __future__ import annotations

import argparse
import csv
import itertools
from pathlib import Path


def safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_." else "-" for char in value)


def read_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(encoding="utf-8", newline="") as file_obj:
        return sorted(
            csv.DictReader(file_obj),
            key=lambda row: (row["doc_title"], int(row.get("page") or 0)),
        )


def render_document(doc_title: str, rows: list[dict[str, str]]) -> str:
    parts = [f"# {doc_title}\n"]
    for row in rows:
        page = row.get("page") or ""
        block_type = row.get("block_type") or ""
        section = row.get("section") or ""
        if section:
            parts.append(f"\n## {section} (p.{page}) [{block_type}]\n")
        else:
            parts.append(f"\n### p.{page} [{block_type}]\n")
        parts.append((row.get("content") or "").strip() + "\n")
    return "".join(parts)


def convert_csv_to_markdown(csv_path: Path, outdir: Path) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    rows = read_rows(csv_path)
    written: list[Path] = []

    for doc_title, group in itertools.groupby(rows, key=lambda row: row["doc_title"]):
        grouped_rows = list(group)
        output_path = outdir / f"{safe_filename(doc_title)}.md"
        output_path.write_text(render_document(doc_title, grouped_rows), encoding="utf-8")
        written.append(output_path)

    return written


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CSV -> Markdown docs")
    parser.add_argument("--csv", required=True, help="Ruta al CSV de entrada")
    parser.add_argument(
        "--outdir",
        default="exports/docs_md",
        help="Carpeta de salida (default: exports/docs_md)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    written = convert_csv_to_markdown(Path(args.csv), Path(args.outdir))
    print(f"OK: {len(written)} documentos Markdown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
