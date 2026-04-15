#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests funcionales para los módulos EusKorpus y las correcciones del pipeline.
"""
import sys
import json
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent  # raíz del repositorio
sys.path.insert(0, str(REPO))

PASS = "[PASS]"
FAIL = "[FAIL]"

results = []

def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    msg = f"{status} {name}"
    if detail:
        msg += f"  →  {detail}"
    print(msg)
    results.append(condition)

# ─────────────────────────────────────────────────────────────
# 1. lang_detect
# ─────────────────────────────────────────────────────────────
print("\n=== lang_detect.py ===")
from scripts.euskorpus.lang_detect import detect_language, annotate_document

# Texto largo en euskera
eu_text = (
    "Hezkuntza sailak ikastetxeetan aplikatzeko araudia onartu du, "
    "eta ikasleek eta irakasleek onartutako xedapenak bete behar dituzte. "
    "Lege hau indarrean sartu zen eta erkidegoaren hezkuntza sisteman garrantzitsua da."
)
res_eu = detect_language(eu_text)
check("lang_detect: euskera detectado", res_eu["language"] == "eu",
      f"language={res_eu['language']} conf={res_eu['confidence']:.2%}")
check("lang_detect: confianza eu > 0.55", res_eu["confidence"] > 0.55,
      f"conf={res_eu['confidence']:.4f}")

# Texto largo en español
es_text = (
    "El decreto establece los requisitos para la prestacion de servicios sanitarios "
    "en los centros hospitalarios de la Comunidad Autonoma. La ley regula la normativa "
    "juridica y las disposiciones legales aplicables al territorio."
)
res_es = detect_language(es_text)
check("lang_detect: español detectado", res_es["language"] == "es",
      f"language={res_es['language']} conf={res_es['confidence']:.2%}")

# Texto muy corto → unknown
res_short = detect_language("Kaixo")
check("lang_detect: texto corto → unknown", res_short["language"] == "unknown",
      f"language={res_short['language']}")

# annotate_document
doc = {"paragraphs": [eu_text, es_text, "Kaixo"]}
annotated = annotate_document(doc)
check("annotate_document: clave creada", "language_annotations" in annotated)
check("annotate_document: 3 anotaciones", len(annotated["language_annotations"]["paragraphs"]) == 3)
check("annotate_document: dominant eu",
      annotated["language_annotations"]["dominant_language"] in ("eu", "es"),
      annotated["language_annotations"]["dominant_language"])

# ─────────────────────────────────────────────────────────────
# 2. domain_classifier
# ─────────────────────────────────────────────────────────────
print("\n=== domain_classifier.py ===")
from scripts.euskorpus.domain_classifier import classify_domain, classify_document

# Texto de salud
health_text = (
    "El decreto regula la prestacion sanitaria y los servicios de salud en los hospitales. "
    "Los pacientes tienen derecho a recibir tratamiento medico adecuado. "
    "La vacunacion es obligatoria segun la normativa sanitaria vigente."
)
res_health = classify_domain(health_text)
check("domain_classifier: health detectado", res_health["domain"] == "health",
      f"domain={res_health['domain']} conf={res_health['confidence']:.2%}")

# Texto educativo
edu_text = (
    "La ley de educacion establece el curriculo para la ensenanza primaria y secundaria. "
    "Los alumnos y profesores deben cumplir con los requisitos de titulacion. "
    "Las becas estan disponibles para estudios universitarios y formacion profesional."
)
res_edu = classify_domain(edu_text)
check("domain_classifier: education detectado", res_edu["domain"] == "education",
      f"domain={res_edu['domain']} conf={res_edu['confidence']:.2%}")

# Texto fiscal
fiscal_text = (
    "El impuesto sobre la renta y el IVA se recaudan por la agencia tributaria. "
    "Los contribuyentes deben presentar la declaracion anual. "
    "Las deducciones fiscales y las exenciones tributarias estan reguladas por ley."
)
res_fiscal = classify_domain(fiscal_text)
check("domain_classifier: fiscal detectado", res_fiscal["domain"] == "fiscal",
      f"domain={res_fiscal['domain']} conf={res_fiscal['confidence']:.2%}")

# classify_document completo
doc2 = {"paragraphs": [health_text, edu_text]}
classified = classify_document(doc2)
check("classify_document: clave creada", "domain_classification" in classified)
check("classify_document: paragraphs anotados",
      len(classified["domain_classification"]["paragraph_domains"]) == 2)

# ─────────────────────────────────────────────────────────────
# 3. json_to_graph: primitivos como propiedades
# ─────────────────────────────────────────────────────────────
print("\n=== json_to_graph.py (primitivos) ===")
sys.path.insert(0, str(REPO / "grafos" / "scripts"))
from json_to_graph import traverse_json

test_obj = {
    "titulo": "Decreto de prueba",
    "anio": 2024,
    "activo": True,
    "tags": ["legal", "eu"],
    "sub": {"clave": "valor"}
}

nodes = {}
rels = []
seen = set()
traverse_json(test_obj, "", "test_source", "", nodes, rels, seen)

root_node = next((n for n in nodes.values() if n.get("path") == ""), None)
check("json_to_graph: nodo raíz existe", root_node is not None)
check("json_to_graph: prop_titulo almacenado",
      root_node is not None and root_node.get("prop_titulo") == "Decreto de prueba",
      str(root_node.get("prop_titulo") if root_node else "NONE"))
check("json_to_graph: prop_anio almacenado",
      root_node is not None and root_node.get("prop_anio") == "2024",
      str(root_node.get("prop_anio") if root_node else "NONE"))
check("json_to_graph: prop_activo almacenado",
      root_node is not None and root_node.get("prop_activo") == "True",
      str(root_node.get("prop_activo") if root_node else "NONE"))
check("json_to_graph: prop_tags (lista primitivos)",
      root_node is not None and root_node.get("prop_tags") == "legal; eu",
      str(root_node.get("prop_tags") if root_node else "NONE"))
check("json_to_graph: sub-dict crea nodo hijo (no prop_sub)",
      root_node is not None and "prop_sub" not in root_node,
      "sub es dict, no debe ser prop")

# ─────────────────────────────────────────────────────────────
# 4. ehaa_scraper: importación y funciones básicas
# ─────────────────────────────────────────────────────────────
print("\n=== ehaa_scraper.py (sin red) ===")
from scripts.euskorpus.ehaa_scraper import (
    parse_bopv_document, clean_text, normalize_unicode, _build_filename
)

html_sample = """
<html><head><title>BOPV 2024-01-15</title>
<meta name="date" content="2024-01-15"/>
</head>
<body>
<h1>Decreto 5/2024, de regulacion educativa</h1>
<h2>I - DISPOSICIONES GENERALES</h2>
<div class="bopv-content">
<p>El Gobierno Vasco aprueba el presente decreto para regular los servicios educativos.</p>
<p>Los centros escolares deberan cumplir con los requisitos establecidos en esta normativa.</p>
</div>
</body></html>
"""

doc_parsed = parse_bopv_document(html_sample, "https://www.euskadi.eus/bopv2/datos/2024/01/15/00012345.shtml", "es")
check("ehaa_scraper: título extraído", "Decreto" in doc_parsed["title"],
      doc_parsed["title"])
check("ehaa_scraper: fecha extraída", doc_parsed["date_published"] == "2024-01-15",
      doc_parsed["date_published"])
check("ehaa_scraper: sección extraída", doc_parsed["section"] is not None,
      doc_parsed["section"])
check("ehaa_scraper: párrafos extraídos", len(doc_parsed["paragraphs"]) >= 1,
      str(len(doc_parsed["paragraphs"])))
check("ehaa_scraper: número de BOPV", doc_parsed["bopv_number"] == "00012345",
      doc_parsed["bopv_number"])

# clean_text
check("ehaa_scraper: clean_text", clean_text("  hola   mundo  ") == "hola mundo")

# _build_filename
fn = _build_filename({"date_published": "2024-01-15", "bopv_number": "00012345", "url": "x"}, "eu")
check("ehaa_scraper: nombre de archivo", fn == "bopv_2024-01-15_00012345_eu.json", fn)

# ─────────────────────────────────────────────────────────────
# Resumen
# ─────────────────────────────────────────────────────────────
passed = sum(results)
total = len(results)
print(f"\n{'='*50}")
print(f"RESULTADO: {passed}/{total} tests pasados")
if passed == total:
    print("TODOS LOS TESTS PASARON ✓")
else:
    print(f"FALLARON: {total - passed} tests")
sys.exit(0 if passed == total else 1)
