#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lang_detect.py - Detector de idioma por párrafo (euskera / español).

Clasifica cada párrafo de un documento como 'eu' (euskera), 'es' (español)
o 'unknown' usando un enfoque híbrido:

1. Lista de palabras frecuentes (stopwords) propias de cada idioma.
2. N-gramas de caracteres con frecuencias típicas.
3. (Opcional) langdetect/langid si están instalados.

Sin dependencias externas obligatorias — funciona sólo con la stdlib.

Uso:
    python lang_detect.py --text "Kaixo mundua, zer moduz?"
    python lang_detect.py --file doc.json --field paragraphs
    python lang_detect.py --help
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Stopwords de referencia
# ---------------------------------------------------------------------------

# Palabras funcionales altamente frecuentes en euskera
_EU_STOPWORDS = frozenset({
    "eta", "da", "ez", "bat", "zer", "nola", "baina", "ere", "zen", "dut",
    "du", "dute", "den", "dela", "dago", "daude", "gara", "dira", "ziren",
    "zuen", "zuten", "izango", "izaten", "behar", "baino", "bai", "hau",
    "hori", "hura", "hauek", "horiek", "haiek", "nik", "zuk", "hark",
    "guk", "zuek", "haiek", "nire", "zure", "bere", "gure", "zure",
    "haien", "honetan", "horretan", "hartan", "dela", "diren", "duen",
    "duten", "arte", "aurre", "gain", "alde", "kontra", "bidez", "baitan",
    "bitarte", "batera", "oraindik", "orain", "bertan", "han", "hemen",
    "oso", "asko", "gutxi", "gehiago", "gutxiago", "beti", "inoiz",
    "egun", "urte", "aste", "hilabete", "lege", "araudi", "agindu",
    "xedapen", "arau", "batzorde", "sail", "eusko", "jaurlaritza",
    "herri", "euskal", "autonomia", "erkidego",
})

# Palabras funcionales altamente frecuentes en español
_ES_STOPWORDS = frozenset({
    "de", "la", "el", "en", "y", "a", "los", "del", "se", "las",
    "un", "por", "con", "una", "su", "al", "lo", "como", "más",
    "pero", "sus", "le", "ya", "o", "fue", "este", "ha", "sí",
    "porque", "esta", "son", "entre", "cuando", "muy", "sin",
    "sobre", "también", "me", "hasta", "hay", "donde", "quien",
    "desde", "todo", "nos", "durante", "estados", "todos", "uno",
    "les", "ni", "contra", "otros", "ese", "eso", "ante", "ellos",
    "e", "esto", "mí", "antes", "algunos", "qué", "unos", "yo",
    "otro", "otras", "él", "tanto", "esa", "estos", "mucho", "quienes",
    "ley", "decreto", "reglamento", "artículo", "gobierno", "vasco",
    "euskadi", "disposición", "normativa",
})

# ---------------------------------------------------------------------------
# N-gramas de caracteres (bigramas/trigramas  típicos de cada idioma)
# ---------------------------------------------------------------------------

# Trigramas muy frecuentes en euskera (corpus BOPV)
_EU_TRIGRAMS = frozenset({
    "ari", "era", "ren", "ean", "tze", "nda", "eko", "eta", "ain",
    "kor", "arr", "irr", "zko", "ald", "ber", "har", "tar", "lar",
    "egi", "len", "bat", "ara", "kin", "all", "urr", "gai", "kon",
    "ran", "dak", "rak", "rre", "tik", "tzu", "zut", "uts",
})

# Trigramas muy frecuentes en español
_ES_TRIGRAMS = frozenset({
    "ión", "de ", " de", "los", "las", "que", " la", "la ", " el",
    "el ", "nte", "ció", "est", "del", "con", "ado", "ara", "nte",
    "ien", "ter", "par", " en", "en ", "pro", "tra", "mie", "nto",
    "ect", "pre", "res", "com", "are", "ble", "ber", "uci", " es",
    "es ", "ste", "aci",
})

# ---------------------------------------------------------------------------
# Características ortográficas
# ---------------------------------------------------------------------------

# Patrones morfológicos exclusivos del euskera
_EU_PATTERNS = [
    re.compile(r"\b\w+(?:arena|aren|arenak|arengandik|arentzat)\b"),   # genitivos
    re.compile(r"\b\w+(?:ekin|tzeko|tzean|tzetik|tzera)\b"),           # sufijos verbales
    re.compile(r"\b(?:ez|bai|baina|ere|ere\s+bai)\b"),                 # partículas
    re.compile(r"\b\w+(?:ko|ka|ke|ki)\b"),                             # locativos
    re.compile(r"(?:tt|dd|rr|ts|tz|tx)"),                              # grupos consonánticos eu
    re.compile(r"\b\w*(?:urruntze|bilketa|aginpide|eskumen)\w*\b"),    # admin. euskera
]

# Patrones morfológicos propios del español
_ES_PATTERNS = [
    re.compile(r"\b\w+(?:ción|ciones|miento|mientos|idad|idades)\b"),
    re.compile(r"\b(?:él|más|así|también|además|según|través)\b"),
    re.compile(r"\b\w+(?:ando|endo|iendo)\b"),                         # gerundios
    re.compile(r"¿|¡"),                                                 # puntuación esp.
    re.compile(r"\b(?:artículo|decreto|ley|reglamento|disposición)\b", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Puntuación y normalización
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """Normaliza a minúsculas, elimina puntuación y acentos."""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")  # quitar diacríticos
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _score_stopwords(tokens: List[str], stopwords: frozenset) -> float:
    """Fracción de tokens que pertenecen al conjunto de stopwords."""
    if not tokens:
        return 0.0
    hits = sum(1 for t in tokens if t in stopwords)
    return hits / len(tokens)


def _score_trigrams(text: str, trigrams: frozenset) -> float:
    """Fracción de trigramas del texto que aparecen en el conjunto dado."""
    all_tg = [text[i : i + 3] for i in range(len(text) - 2)]
    if not all_tg:
        return 0.0
    hits = sum(1 for tg in all_tg if tg in trigrams)
    return hits / len(all_tg)


def _score_patterns(text: str, patterns: List[re.Pattern]) -> float:
    """Número de patrones morfológicos que coinciden (normalizado)."""
    total = sum(len(p.findall(text)) for p in patterns)
    words = len(text.split())
    if not words:
        return 0.0
    return min(total / words, 1.0)


# ---------------------------------------------------------------------------
# Detección principal
# ---------------------------------------------------------------------------

# Pesos para combinar señales
_W_STOPWORD = 0.45
_W_TRIGRAM = 0.30
_W_PATTERN = 0.25


def detect_language(text: str, min_chars: int = 15) -> Dict:
    """
    Detecta el idioma de un fragmento de texto.

    Args:
        text:      Texto a clasificar.
        min_chars: Mínimo de caracteres; textos más cortos devuelven 'unknown'.

    Returns:
        Dict con claves:
            - language: "eu" | "es" | "unknown"
            - confidence: float 0-1
            - scores: {"eu": float, "es": float}
            - method: str  (descripción del método utilizado)
    """
    text = text.strip()
    if len(text) < min_chars:
        return {"language": "unknown", "confidence": 0.0, "scores": {"eu": 0.0, "es": 0.0}, "method": "too_short"}

    # 1. Intentar con librería externa si está disponible
    external = _try_external_detector(text)
    if external:
        return external

    # 2. Método interno basado en señales léxicas y morfológicas
    norm = _normalize(text)
    tokens = norm.split()

    sw_eu = _score_stopwords(tokens, _EU_STOPWORDS)
    sw_es = _score_stopwords(tokens, _ES_STOPWORDS)

    tg_eu = _score_trigrams(norm, _EU_TRIGRAMS)
    tg_es = _score_trigrams(norm, _ES_TRIGRAMS)

    pt_eu = _score_patterns(text.lower(), _EU_PATTERNS)
    pt_es = _score_patterns(text.lower(), _ES_PATTERNS)

    score_eu = _W_STOPWORD * sw_eu + _W_TRIGRAM * tg_eu + _W_PATTERN * pt_eu
    score_es = _W_STOPWORD * sw_es + _W_TRIGRAM * tg_es + _W_PATTERN * pt_es

    total = score_eu + score_es
    if total < 1e-9:
        return {"language": "unknown", "confidence": 0.0, "scores": {"eu": 0.0, "es": 0.0}, "method": "internal"}

    conf_eu = score_eu / total
    conf_es = score_es / total

    if conf_eu > conf_es:
        lang, conf = "eu", conf_eu
    else:
        lang, conf = "es", conf_es

    # Umbral mínimo de confianza: si ambos son muy bajos → unknown
    if max(conf_eu, conf_es) < 0.52:
        lang, conf = "unknown", max(conf_eu, conf_es)

    return {
        "language": lang,
        "confidence": round(conf, 4),
        "scores": {"eu": round(conf_eu, 4), "es": round(conf_es, 4)},
        "method": "internal",
    }


def _try_external_detector(text: str) -> Optional[Dict]:
    """Intenta usar langdetect o langid si están instalados."""
    try:
        from langdetect import detect, detect_langs  # type: ignore

        results = detect_langs(text)
        for r in results:
            if r.lang in ("eu", "es"):
                return {
                    "language": r.lang,
                    "confidence": round(r.prob, 4),
                    "scores": {rr.lang: round(rr.prob, 4) for rr in results if rr.lang in ("eu", "es")},
                    "method": "langdetect",
                }
    except Exception:
        pass

    try:
        import langid  # type: ignore

        langid.set_languages(["eu", "es"])
        lang, conf = langid.classify(text)
        return {
            "language": lang,
            "confidence": round(abs(conf), 4),
            "scores": {lang: round(abs(conf), 4)},
            "method": "langid",
        }
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Procesamiento de documentos JSON
# ---------------------------------------------------------------------------


def annotate_document(doc: Dict, field: str = "paragraphs") -> Dict:
    """
    Añade anotaciones de idioma a cada párrafo de un documento.

    La función agrega/actualiza la clave ``language_annotations`` en el documento::

        {
          "language_annotations": {
            "paragraphs": [
              {"index": 0, "language": "eu", "confidence": 0.87},
              ...
            ],
            "dominant_language": "eu",
            "eu_ratio": 0.94
          }
        }
    """
    paragraphs = doc.get(field, [])
    if not isinstance(paragraphs, list):
        paragraphs = [str(paragraphs)]

    annotations = []
    for i, para in enumerate(paragraphs):
        if not isinstance(para, str):
            para = json.dumps(para, ensure_ascii=False)
        result = detect_language(para)
        annotations.append(
            {
                "index": i,
                "language": result["language"],
                "confidence": result["confidence"],
                "method": result["method"],
            }
        )

    # Calcular idioma dominante
    lang_counts: Dict[str, int] = {}
    for ann in annotations:
        lang = ann["language"]
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

    total = len(annotations)
    dominant = max(lang_counts, key=lang_counts.get) if lang_counts else "unknown"
    eu_count = lang_counts.get("eu", 0)
    eu_ratio = round(eu_count / total, 4) if total else 0.0

    doc["language_annotations"] = {
        "field": field,
        "paragraphs": annotations,
        "dominant_language": dominant,
        "eu_ratio": eu_ratio,
        "lang_counts": lang_counts,
    }
    return doc


def process_json_file(input_path: Path, output_path: Optional[Path], field: str) -> Dict:
    """Lee un JSON, anota idioma por párrafo y guarda el resultado."""
    with open(input_path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)

    annotated = annotate_document(doc, field)

    out = output_path or input_path
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(annotated, fh, ensure_ascii=False, indent=2)

    return annotated


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lang_detect",
        description="Detector de idioma por párrafo (euskera / español).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", metavar="TEXTO", help="Texto a clasificar directamente")
    group.add_argument("--file", metavar="PATH", help="Archivo JSON a anotar")

    parser.add_argument(
        "--field",
        metavar="CAMPO",
        default="paragraphs",
        help="Campo JSON que contiene la lista de párrafos (default: paragraphs)",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        default=None,
        help="Ruta de salida del JSON anotado (default: sobreescribe el original)",
    )
    parser.add_argument("--json", action="store_true", dest="json_out", help="Salida en JSON")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.text:
        result = detect_language(args.text)
        if args.json_out:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Idioma: {result['language']}  (confianza: {result['confidence']:.0%}, método: {result['method']})")
            print(f"Puntuaciones — eu: {result['scores']['eu']:.4f}  es: {result['scores']['es']:.4f}")
        return 0

    if args.file:
        input_path = Path(args.file)
        output_path = Path(args.output) if args.output else None
        annotated = process_json_file(input_path, output_path, args.field)
        ann = annotated.get("language_annotations", {})
        print(f"Idioma dominante: {ann.get('dominant_language')}  (ratio eu: {ann.get('eu_ratio', 0):.0%})")
        print(f"Párrafos anotados: {len(ann.get('paragraphs', []))}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
