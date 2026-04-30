from __future__ import annotations

import importlib

MODULES = [
    "scripts.euskorpus.ehaa_scraper",
    "scripts.euskorpus.lang_detect",
    "scripts.euskorpus.domain_classifier",
    "scripts.tratamiento_datos.csv_to_md",
    "scripts.tratamiento_datos.csv_to_json",
    "scripts.tratamiento_datos.json_to_csv",
    "scripts.tratamiento_datos.csv_to_md_chunks",
    "scripts.tratamiento_datos.json_to_pdf",
    "scripts.tratamiento_datos.json_to_dual_pdf",
    "grafos.scripts.run_pipeline_to_neo4j",
]


def test_modules_import_without_side_effects() -> None:
    for module in MODULES:
        importlib.import_module(module)
