#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
domain_classifier.py - Clasificador de dominio temático para textos legales vascos.

Clasifica documentos y párrafos en dominios principales:
  - legal      (disposiciones, leyes, decretos, normativa general)
  - health     (sanidad, salud pública, farmacia, servicios sociales)
  - education  (educación, enseñanza, universidades, formación)
  - fiscal     (tributación, hacienda, impuestos, presupuestos)
  - other      (no clasificado con suficiente confianza)

El clasificador usa un enfoque de similitud léxica (bag-of-words pesado) sin
dependencias externas obligatorias. Opcionalmente se puede integrar un modelo
de Hugging Face si está disponible.

Uso:
    python domain_classifier.py --text "El decreto regula la prestación sanitaria..."
    python domain_classifier.py --file doc.json --field paragraphs
    python domain_classifier.py --help
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Vocabularios por dominio (es + eu mezclados, ponderados)
# ---------------------------------------------------------------------------

# Cada entrada: (término, peso)
# Peso 2 → término muy discriminativo; peso 1 → término general del dominio

DOMAIN_VOCAB: Dict[str, List[Tuple[str, int]]] = {
    "legal": [
        ("ley", 2), ("decreto", 2), ("reglamento", 2), ("disposición", 2),
        ("artículo", 1), ("normativa", 2), ("legislación", 2), ("orden", 1),
        ("resolución", 2), ("acuerdo", 1), ("constitución", 2), ("código", 1),
        ("jurídico", 2), ("tribunal", 2), ("juzgado", 2), ("sentencia", 2),
        ("contrato", 1), ("convenio", 1), ("derecho", 1), ("obligación", 1),
        ("sanción", 1), ("infracción", 1), ("expediente", 1), ("registro", 1),
        ("publicación", 1), ("boletín", 2), ("oficial", 1), ("vigencia", 2),
        # euskera
        ("lege", 2), ("dekretua", 2), ("araudi", 2), ("xedapen", 2),
        ("ebazpen", 2), ("agindua", 2), ("araua", 1), ("eskubide", 1),
        ("betebehar", 1), ("zigor", 1), ("epai", 2), ("auzitegi", 2),
        ("kontratuak", 1), ("argitarapen", 1), ("indarrean", 2),
    ],
    "health": [
        ("salud", 2), ("sanidad", 2), ("sanitario", 2), ("sanitaria", 2),
        ("médico", 2), ("médica", 2), ("hospital", 2), ("clínica", 2),
        ("farmacia", 2), ("medicamento", 2), ("paciente", 2), ("enfermedad", 2),
        ("diagnóstico", 2), ("tratamiento", 2), ("asistencia", 1), ("prestación", 1),
        ("epidemia", 2), ("vacuna", 2), ("higiene", 1), ("prevención", 1),
        ("servicio social", 2), ("dependencia", 1), ("discapacidad", 2),
        ("osakidetza", 2), ("bienestar", 1), ("social", 1),
        # euskera
        ("osasuna", 2), ("osasungintza", 2), ("ospitale", 2), ("botika", 2),
        ("gaixo", 2), ("gaixotasun", 2), ("tratamendu", 2), ("prebentzio", 2),
        ("txertoa", 2), ("gizarte zerbitzu", 2), ("mendetasun", 1),
        ("desgaitasun", 2), ("ongizate", 1),
    ],
    "education": [
        ("educación", 2), ("enseñanza", 2), ("escuela", 2), ("colegio", 2),
        ("universidad", 2), ("alumno", 1), ("profesor", 1), ("docente", 2),
        ("currículum", 2), ("currículo", 2), ("materia", 1), ("asignatura", 2),
        ("formación", 1), ("titulación", 2), ("título", 1), ("grado", 1),
        ("bachillerato", 2), ("primaria", 2), ("secundaria", 2), ("infantil", 1),
        ("beca", 2), ("aprendizaje", 1), ("evaluación", 1), ("ikastola", 2),
        ("lanbide", 2), ("hezkuntza", 2),
        # euskera
        ("hezkuntza", 2), ("ikasle", 2), ("irakasle", 2), ("eskola", 2),
        ("unibertsitate", 2), ("curriculum", 2), ("ikasketa", 2), ("titulazio", 2),
        ("lanbide heziketa", 2), ("irakaskuntza", 2), ("ebaluazio", 1),
        ("beka", 2), ("ikastola", 2),
    ],
    "fiscal": [
        ("impuesto", 2), ("tributario", 2), ("tributo", 2), ("fiscal", 2),
        ("hacienda", 2), ("presupuesto", 2), ("recaudación", 2), ("irpf", 2),
        ("iva", 2), ("renta", 1), ("declaración", 1), ("devolución", 1),
        ("deducción", 2), ("exención", 2), ("base imponible", 2), ("tipo", 1),
        ("contribuyente", 2), ("obligado tributario", 2), ("agencia tributaria", 2),
        ("financiación", 1), ("ingreso", 1), ("gasto", 1), ("partida", 1),
        ("licitación", 2), ("contratación pública", 2),
        # euskera
        ("zerga", 2), ("ogasun", 2), ("aurrekontu", 2), ("bilketa", 2),
        ("pfez", 2), ("bfa", 2), ("aitorpen", 2), ("itzulketa", 2),
        ("kenkaria", 2), ("salbuespena", 2), ("zergadun", 2), ("diru sarrera", 1),
        ("gastuak", 1), ("lizitazio", 2), ("kontratazio publiko", 2),
    ],
}

# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """Minúsculas, sin diacríticos, sin puntuación."""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

# Umbral mínimo de confianza para asignar un dominio distinto de "other"
_CONFIDENCE_THRESHOLD = 0.30


def classify_domain(text: str) -> Dict:
    """
    Clasifica el texto en un dominio temático.

    Returns:
        {
          "domain": "legal" | "health" | "education" | "fiscal" | "other",
          "confidence": float,   # 0-1
          "scores": {"legal": float, ...},
          "method": str
        }
    """
    if not text or len(text.strip()) < 10:
        return {
            "domain": "other",
            "confidence": 0.0,
            "scores": {d: 0.0 for d in DOMAIN_VOCAB},
            "method": "too_short",
        }

    # Intentar clasificador externo primero
    external = _try_external_classifier(text)
    if external:
        return external

    norm = _normalize(text)
    raw_scores: Dict[str, float] = {}

    for domain, vocab in DOMAIN_VOCAB.items():
        score = 0.0
        for term, weight in vocab:
            # Buscar la frase exacta (o palabra) como token(s) completos
            pattern = r"\b" + re.escape(term) + r"\b"
            matches = len(re.findall(pattern, norm))
            score += matches * weight
        raw_scores[domain] = score

    total = sum(raw_scores.values())
    if total < 1e-9:
        return {
            "domain": "other",
            "confidence": 0.0,
            "scores": {d: 0.0 for d in DOMAIN_VOCAB},
            "method": "internal",
        }

    norm_scores = {d: round(s / total, 4) for d, s in raw_scores.items()}
    best_domain = max(norm_scores, key=norm_scores.get)
    best_conf = norm_scores[best_domain]

    if best_conf < _CONFIDENCE_THRESHOLD:
        best_domain = "other"

    return {
        "domain": best_domain,
        "confidence": round(best_conf, 4),
        "scores": norm_scores,
        "method": "internal",
    }


def _try_external_classifier(text: str) -> Optional[Dict]:
    """Usa un modelo Hugging Face si está disponible (clasificación zero-shot)."""
    try:
        from transformers import pipeline  # type: ignore

        candidate_labels = list(DOMAIN_VOCAB.keys())
        classifier = pipeline("zero-shot-classification", model="typeform/distilbert-base-uncased-mnli")
        result = classifier(text[:512], candidate_labels=candidate_labels)

        scores = dict(zip(result["labels"], [round(s, 4) for s in result["scores"]]))
        best = result["labels"][0]
        conf = round(result["scores"][0], 4)

        if conf < _CONFIDENCE_THRESHOLD:
            best = "other"

        return {
            "domain": best,
            "confidence": conf,
            "scores": scores,
            "method": "zero-shot-transformers",
        }
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Procesamiento de documentos
# ---------------------------------------------------------------------------


def classify_paragraphs(paragraphs: List[str]) -> List[Dict]:
    """Clasifica cada párrafo individualmente."""
    results = []
    for i, para in enumerate(paragraphs):
        if not isinstance(para, str):
            para = json.dumps(para, ensure_ascii=False)
        result = classify_domain(para)
        results.append({"index": i, **result})
    return results


def classify_document(doc: Dict, field: str = "paragraphs") -> Dict:
    """
    Clasifica el dominio de un documento completo y por párrafo.

    Añade/actualiza la clave ``domain_classification`` en el documento::

        {
          "domain_classification": {
            "document_domain": "legal",
            "document_confidence": 0.72,
            "paragraph_domains": [
              {"index": 0, "domain": "legal", "confidence": 0.81, ...},
              ...
            ],
            "domain_distribution": {"legal": 0.80, "fiscal": 0.15, ...}
          }
        }
    """
    paragraphs = doc.get(field, [])
    if isinstance(paragraphs, str):
        paragraphs = [paragraphs]

    # Clasificar el documento completo (concatenación de todos los párrafos)
    full_text = " ".join(str(p) for p in paragraphs)
    doc_result = classify_domain(full_text)

    # Clasificar por párrafo
    para_results = classify_paragraphs(paragraphs)

    # Distribución de dominios a nivel de párrafo
    domain_counts: Dict[str, int] = {}
    for pr in para_results:
        d = pr["domain"]
        domain_counts[d] = domain_counts.get(d, 0) + 1

    total = len(para_results)
    domain_dist = {d: round(c / total, 4) for d, c in domain_counts.items()} if total else {}

    doc["domain_classification"] = {
        "field": field,
        "document_domain": doc_result["domain"],
        "document_confidence": doc_result["confidence"],
        "document_scores": doc_result["scores"],
        "paragraph_domains": para_results,
        "domain_distribution": domain_dist,
        "method": doc_result["method"],
    }
    return doc


def process_json_file(input_path: Path, output_path: Optional[Path], field: str) -> Dict:
    """Lee un JSON, clasifica dominio y guarda el resultado."""
    with open(input_path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)

    classified = classify_document(doc, field)

    out = output_path or input_path
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(classified, fh, ensure_ascii=False, indent=2)

    return classified


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="domain_classifier",
        description="Clasificador de dominio temático para textos legales vascos.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", metavar="TEXTO", help="Texto a clasificar directamente")
    group.add_argument("--file", metavar="PATH", help="Archivo JSON a clasificar")

    parser.add_argument(
        "--field",
        metavar="CAMPO",
        default="paragraphs",
        help="Campo JSON con la lista de párrafos (default: paragraphs)",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        default=None,
        help="Ruta de salida del JSON clasificado (default: sobreescribe el original)",
    )
    parser.add_argument("--json", action="store_true", dest="json_out", help="Salida en JSON")
    parser.add_argument(
        "--threshold",
        type=float,
        metavar="FLOAT",
        default=_CONFIDENCE_THRESHOLD,
        help=f"Umbral mínimo de confianza para asignar dominio (default: {_CONFIDENCE_THRESHOLD})",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    # Permitir override del umbral
    global _CONFIDENCE_THRESHOLD
    _CONFIDENCE_THRESHOLD = args.threshold

    if args.text:
        result = classify_domain(args.text)
        if args.json_out:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Dominio: {result['domain']}  (confianza: {result['confidence']:.0%}, método: {result['method']})")
            for d, s in sorted(result["scores"].items(), key=lambda x: -x[1]):
                print(f"  {d:<12} {s:.4f}")
        return 0

    if args.file:
        input_path = Path(args.file)
        output_path = Path(args.output) if args.output else None
        classified = process_json_file(input_path, output_path, args.field)
        dc = classified.get("domain_classification", {})
        print(f"Dominio documento: {dc.get('document_domain')}  (confianza: {dc.get('document_confidence', 0):.0%})")
        print(f"Distribución por párrafo: {dc.get('domain_distribution')}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
