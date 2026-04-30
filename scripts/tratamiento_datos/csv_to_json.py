#!/usr/bin/env python3
"""Convierte CSV de bloques DI a NDJSON compatible con Azure AI Search."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


def slug(value: str | None) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value or "").strip("-")[:64]


def row_to_search_doc(row: dict[str, str], index: int) -> dict[str, object]:
    return {
        "@search.action": "mergeOrUpload",
        "id": f"{slug(row.get('doc_title'))}-p{row.get('page', '0')}-{index:06d}",
        "content": row.get("content", ""),
        "doc_title": row.get("doc_title", ""),
        "page": int(row.get("page") or 0),
        "block_type": row.get("block_type", ""),
        "role": row.get("role", ""),
        "section": row.get("section", ""),
        "source": "pdf",
        "lang": "es",
    }


def convert_csv_to_ndjson(csv_path: Path, output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with csv_path.open(encoding="utf-8", newline="") as file_obj:
        with output_path.open("w", encoding="utf-8") as output_obj:
            reader = csv.DictReader(file_obj)
            for count, row in enumerate(reader, start=1):
                output_obj.write(
                    json.dumps(row_to_search_doc(row, count), ensure_ascii=False) + "\n"
                )
    return count


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CSV -> NDJSON (Azure AI Search u otros)")
    parser.add_argument("--csv", required=True, help="Ruta al CSV de entrada")
    parser.add_argument(
        "--out",
        default="exports/csv/export_azure.ndjson",
        help="Ruta NDJSON de salida (default: exports/csv/export_azure.ndjson)",
    )
    parser.add_argument("--index-name", default="invk-ocr-chunks", help="Nombre de indice")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    count = convert_csv_to_ndjson(Path(args.csv), Path(args.out))
    print(f"OK: {count} documentos NDJSON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
