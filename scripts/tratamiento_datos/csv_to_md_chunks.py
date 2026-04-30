#!/usr/bin/env python3
"""Convierte un CSV de bloques DI a chunks Markdown para RAG."""

from __future__ import annotations

import argparse
import csv
import textwrap
from pathlib import Path


def render_chunk(row: dict[str, str]) -> str:
    title = row.get("doc_title", "")
    page = row.get("page", "")
    block_type = row.get("block_type", "")
    section = row.get("section", "")
    content = row.get("content", "").strip()

    body = f"# {title} - p.{page} [{block_type}]\n"
    if section:
        body += f"**{section}**\n\n"
    return body + textwrap.dedent(content) + "\n"


def convert_csv_to_markdown_chunks(csv_path: Path, outdir: Path, prefix: str = "") -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with csv_path.open(encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        for index, row in enumerate(reader, start=1):
            output_path = outdir / f"{prefix}{index:05d}.md"
            output_path.write_text(render_chunk(row), encoding="utf-8")
            written.append(output_path)
    return written


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CSV -> MD chunks (para RAG)")
    parser.add_argument("--csv", required=True, help="Ruta al CSV de entrada")
    parser.add_argument(
        "--outdir",
        default="exports/md_chunks",
        help="Carpeta de salida (default: exports/md_chunks)",
    )
    parser.add_argument("--prefix", default="", help="Prefijo de nombre de archivo")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    written = convert_csv_to_markdown_chunks(Path(args.csv), Path(args.outdir), args.prefix)
    print(f"OK: {len(written)} chunks Markdown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
