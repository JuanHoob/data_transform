#!/usr/bin/env python3
"""Validador ligero de CSV sin rutas hardcodeadas."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

DEFAULT_FIELD_SIZE_LIMIT = 131_072 * 10


def validate_csv_file(
    csv_path: Path, field_size_limit: int = DEFAULT_FIELD_SIZE_LIMIT
) -> dict[str, int | str]:
    """Lee un CSV completo y devuelve metricas basicas si es valido."""
    csv.field_size_limit(field_size_limit)
    with csv_path.open(encoding="utf-8", newline="") as file_obj:
        reader = csv.reader(file_obj)
        row_count = sum(1 for _ in reader)
    return {"path": str(csv_path), "rows": row_count}


def write_report(report_path: Path, report: dict[str, int | str]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Valida que un archivo CSV se pueda leer completo."
    )
    parser.add_argument("csv_file", help="Ruta al CSV que se quiere validar")
    parser.add_argument("--report", help="Ruta opcional a un reporte JSON")
    parser.add_argument(
        "--field-size-limit",
        type=int,
        default=DEFAULT_FIELD_SIZE_LIMIT,
        help=f"Limite de tamano de campo CSV (default: {DEFAULT_FIELD_SIZE_LIMIT})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"CSV no encontrado: {csv_path}")
        return 1

    try:
        report = validate_csv_file(csv_path, args.field_size_limit)
    except Exception as exc:
        print(f"CSV invalido: {csv_path} ({exc})")
        return 1

    if args.report:
        write_report(Path(args.report), report)

    print(f"CSV valido - {report['rows']} filas leidas correctamente")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
