#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filtro de limpieza para JSON (Azure DI / OCR / genéricos).

- Recorre el JSON completo y limpia todas las cadenas (o solo ciertas claves).
- Normaliza Unicode (NFC).
- Elimina controles (salvo \n y \t), PUA y no-asignados.
- Colapsa espacios raros a ' ' y borra zero-widths.
- Mapea glifos problemáticos a ASCII/Unicode estándar (comillas, rayas, NBSP, BOM, ...).
- Reporte CSV con métricas por archivo.

Estructura esperada del repo del usuario:
  - Entrada por defecto:  data/brutos_json
  - Salida por defecto:   data/limpios_json
  - Reporte por defecto:  infodoc/clean_report.csv

Uso típico (PowerShell):
  # Simulación (no escribe archivos)
  python scripts/limpiezaD/clean_json_text.py `
      --in data\\brutos_json `
      --out data\\limpios_json `
      --report infodoc\\clean_report.csv `
      --ext .json `
      --dry-run

  # Escritura real
  python scripts/limpiezaD/clean_json_text.py `
      --in data\\brutos_json `
      --out data\\limpios_json `
      --report infodoc\\clean_report.csv `
      --ext .json `
      --overwrite

Para un archivo concreto:
  python scripts/limpiezaD/clean_json_text.py --in data\\brutos_json\\archivo.json --out data\\limpios_json --report infodoc\\clean_report.csv --overwrite

Requisitos: solo librerías estándar (argparse, json, unicodedata, etc.). PyYAML opcional si usas --rules.
"""

from __future__ import annotations
import argparse
import json
import os
import re
import sys
import unicodedata
from typing import Any, Dict, Iterable, Tuple, List, Union

try:
    import yaml  # opcional
except Exception:
    yaml = None

# ----------------------------
# Config base / mapeos
# ----------------------------

# Controles permitidos explícitos:
_ALLOWED_CONTROLS = {"\n", "\t"}

# Mapeos comunes de glifos problemáticos -> equivalentes
COMMON_MAP: Dict[str, str] = {
    "\u00A0": " ",   # NBSP
    "\u2007": " ",   # Figure space
    "\u2009": " ",   # Thin space
    "\u202F": " ",   # Narrow NBSP
    "\u200B": "",    # Zero-width space
    "\u200C": "",    # ZWNJ
    "\u200D": "",    # ZWJ
    "\u2060": "",    # Word joiner
    "\uFEFF": "",    # BOM

    "“": "\"", "”": "\"", "„": "\"",
    "‘": "'",  "’": "'",
    "‐": "-", "–": "-", "—": "-",
    "…": "...",
}

# Regex para colapsar espacios raros a un único espacio
RE_SPACES = re.compile(r"[ \t\u00A0\u2000-\u200B\u202F\u2060\uFEFF]+")

# Claves típicas de texto (si se usa --keys-only)
LIKELY_TEXT_KEYS = {
    "text", "content", "value", "line", "paragraph", "span", "title", "caption", "heading"
}


# ----------------------------
# Utilidades
# ----------------------------

def load_rules(path: str | None) -> Dict[str, Any]:
    """Carga mapa/flags desde YAML opcional: { replace: {from: to}, keep_controls: [..] }."""
    if not path:
        return {}
    if yaml is None:
        print("[WARN] PyYAML no instalado; ignorando --rules.", file=sys.stderr)
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def is_allowed_char(ch: str, allowed_controls: Iterable[str]) -> bool:
    """Permite letras, números, puntuación normal; bloquea controles (salvo permitidos), PUA y no-asignados."""
    if ch in allowed_controls:
        return True
    cat = unicodedata.category(ch)
    if cat == "Cc":   # control char
        return False
    if cat in {"Cs", "Cn"}:  # surrogate / unassigned
        return False
    code = ord(ch)
    # Private Use Areas
    if (0xE000 <= code <= 0xF8FF) or (0xF0000 <= code <= 0xFFFFD) or (0x100000 <= code <= 0x10FFFD):
        return False
    return True


def apply_common_map(s: str, mapping: Dict[str, str]) -> Tuple[str, int]:
    """Aplica reemplazos de COMMON_MAP y devuelve (texto, chars_mapeados)."""
    if not mapping:
        return s, 0
    count = 0
    out = []
    for ch in s:
        if ch in mapping:
            out.append(mapping[ch])
            count += 1
        else:
            out.append(ch)
    return "".join(out), count


def clean_string(
    s: str,
    mapping: Dict[str, str],
    allowed_controls: Iterable[str]
) -> Tuple[str, Dict[str, int]]:
    """Limpia una cadena y devuelve (texto_limpio, métricas)."""
    orig_len = len(s)
    metrics = {
        "chars_in": orig_len,
        "chars_removed": 0,
        "chars_mapped": 0,
        "changed": 0,
    }

    # Normaliza
    s_norm = unicodedata.normalize("NFC", s)

    # Reemplazos comunes
    s_map, mapped = apply_common_map(s_norm, mapping)
    metrics["chars_mapped"] += mapped

    # Filtra caracteres no permitidos
    filtered_chars = []
    removed = 0
    for ch in s_map:
        if is_allowed_char(ch, allowed_controls):
            filtered_chars.append(ch)
        else:
            removed += 1
    s_filt = "".join(filtered_chars)
    metrics["chars_removed"] += removed

    # Colapsa espacios “raros” a un único espacio
    s_space = RE_SPACES.sub(" ", s_filt)

    # Limpieza final de espacios repetidos
    s_final = re.sub(r"[ ]{2,}", " ", s_space)

    if s_final != s:
        metrics["changed"] = 1

    return s_final, metrics


def should_clean_key(key: Any, keys_only: bool, allowed_keys: set[str]) -> bool:
    if not keys_only:
        return True
    if isinstance(key, str):
        return key in allowed_keys
    return False


def walk_and_clean(obj: Any, keys_only: bool, allowed_keys: set[str], mapping: Dict[str, str], allowed_controls: Iterable[str]) -> Tuple[Any, Dict[str, int]]:
    """Recorre el objeto, limpia strings y acumula métricas globales."""
    agg = {
        "strings_total": 0,
        "strings_changed": 0,
        "chars_removed": 0,
        "chars_mapped": 0,
    }

    def merge(m: Dict[str, int]):
        agg["strings_total"]   += 1
        agg["strings_changed"] += m.get("changed", 0)
        agg["chars_removed"]   += m.get("chars_removed", 0)
        agg["chars_mapped"]    += m.get("chars_mapped", 0)

    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(v, str) and should_clean_key(k, keys_only, allowed_keys):
                cleaned, m = clean_string(v, mapping, allowed_controls)
                out[k] = cleaned
                merge(m)
            else:
                new_v, subm = walk_and_clean(v, keys_only, allowed_keys, mapping, allowed_controls)
                out[k] = new_v
                for kk in agg:
                    agg[kk] += subm.get(kk, 0)
        return out, agg

    if isinstance(obj, list):
        out_list = []
        for item in obj:
            if isinstance(item, str) and not keys_only:
                cleaned, m = clean_string(item, mapping, allowed_controls)
                out_list.append(cleaned)
                merge(m)
            else:
                new_item, subm = walk_and_clean(item, keys_only, allowed_keys, mapping, allowed_controls)
                out_list.append(new_item)
                for kk in agg:
                    agg[kk] += subm.get(kk, 0)
        return out_list, agg

    if isinstance(obj, str) and not keys_only:
        cleaned, m = clean_string(obj, mapping, allowed_controls)
        merge(m)
        return cleaned, agg

    return obj, agg


def iter_input_paths(in_path: str, ext: str) -> Iterable[str]:
    """Devuelve rutas de entrada: archivo directo o todos los .ext del directorio."""
    if os.path.isfile(in_path):
        return [in_path]
    if os.path.isdir(in_path):
        out = []
        for name in os.listdir(in_path):
            if ext and not name.lower().endswith(ext.lower()):
                continue
            out.append(os.path.join(in_path, name))
        return sorted(out)
    raise FileNotFoundError(f"No existe la ruta de entrada: {in_path}")


def ensure_dir(path: str) -> None:
    if path and not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


# ----------------------------
# CLI
# ----------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Limpieza de JSON (Unicode/textos problemáticos).")
    ap.add_argument("--in", dest="in_path", required=True, help="Archivo JSON o carpeta (p. ej., data/brutos_json)")
    ap.add_argument("--out", dest="out_dir", default="data/limpios_json", help="Carpeta de salida (por defecto: data/limpios_json)")
    ap.add_argument("--report", default="infodoc/clean_report.csv", help="CSV de métricas (por defecto: infodoc/clean_report.csv)")
    ap.add_argument("--ext", default=".json", help="Extensión a filtrar cuando --in es carpeta (por defecto: .json)")
    ap.add_argument("--overwrite", action="store_true", help="Sobrescribe si el destino ya existe")
    ap.add_argument("--dry-run", action="store_true", help="No escribe archivos, solo calcula métricas")
    ap.add_argument("--keys-only", action="count", default=0,
                    help="Limpiar solo claves de texto típicas (usa una vez). Usa dos veces para pasar una lista personalizada vía --keys.")
    ap.add_argument("--keys", nargs="*", default=None, help="Lista de claves a limpiar cuando usas --keys-only dos veces")
    ap.add_argument("--rules", default=None, help="YAML opcional con {replace: {from: to}, keep_controls: ['\\n','\\t']}")
    return ap.parse_args()


def main():
    args = parse_args()

    # Reglas opcionales
    rules = load_rules(args.rules)
    mapping = dict(COMMON_MAP)
    if isinstance(rules.get("replace"), dict):
        # convierte claves a str explícita
        mapping.update({str(k): str(v) for k, v in rules["replace"].items()})

    allowed_controls = set(_ALLOWED_CONTROLS)
    kc = rules.get("keep_controls")
    if isinstance(kc, list):
        allowed_controls |= {str(x) for x in kc}

    # Modo "solo ciertas claves"
    allowed_keys = set(LIKELY_TEXT_KEYS)
    if args.keys_only >= 2 and args.keys:
        allowed_keys = set(args.keys)

    input_paths = list(iter_input_paths(args.in_path, args.ext))
    if not input_paths:
        print("No hay entradas que procesar.", file=sys.stderr)
        sys.exit(2)

    if not args.dry_run:
        ensure_dir(args.out_dir)
        ensure_dir(os.path.dirname(args.report))

    # Reporte
    header = ["file_in", "file_out", "strings_total", "strings_changed", "chars_removed", "chars_mapped", "written"]
    report_rows: List[List[Union[str, int]]] = []

    for src in input_paths:
        try:
            with open(src, "r", encoding="utf-8") as f:
                obj = json.load(f)
        except Exception as e:
            print(f"[WARN] No se pudo leer {src}: {e}", file=sys.stderr)
            continue

        cleaned, metrics = walk_and_clean(
            obj=obj,
            keys_only=bool(args.keys_only),
            allowed_keys=allowed_keys,
            mapping=mapping,
            allowed_controls=allowed_controls
        )

        # Destino
        if os.path.isdir(args.in_path):
            fname = os.path.basename(src)
            dst = os.path.join(args.out_dir, fname)
        else:
            # si es archivo único, mantiene nombre en out_dir
            fname = os.path.basename(src)
            dst = os.path.join(args.out_dir, fname)

        written = "no"
        if not args.dry_run:
            if os.path.exists(dst) and not args.overwrite:
                print(f"[SKIP] Existe y no se permite overwrite: {dst}")
            else:
                try:
                    with open(dst, "w", encoding="utf-8") as fo:
                        json.dump(cleaned, fo, ensure_ascii=False, indent=2)
                    written = "yes"
                except Exception as e:
                    print(f"[ERR ] No se pudo escribir {dst}: {e}", file=sys.stderr)

        report_rows.append([
            os.path.relpath(src),
            os.path.relpath(dst) if not args.dry_run else "",
            metrics["strings_total"],
            metrics["strings_changed"],
            metrics["chars_removed"],
            metrics["chars_mapped"],
            written
        ])

        print(f"[OK ] {os.path.relpath(src)}  ->  strings:{metrics['strings_total']}  "
              f"changed:{metrics['strings_changed']}  removed:{metrics['chars_removed']}  mapped:{metrics['chars_mapped']}  "
              f"{'(dry-run)' if args.dry_run else ''}")

    # Escribe reporte
    try:
        if not args.dry_run:
            import csv
            with open(args.report, "w", encoding="utf-8", newline="") as rf:
                w = csv.writer(rf)
                w.writerow(header)
                w.writerows(report_rows)
            print(f"[REPORT] {os.path.abspath(args.report)}")
        else:
            print("[REPORT] Dry-run: no se escribió CSV (usa --report sin --dry-run).")
    except Exception as e:
        print(f"[WARN] No se pudo escribir el reporte: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
