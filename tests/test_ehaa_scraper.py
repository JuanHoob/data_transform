from __future__ import annotations

from scripts.euskorpus.ehaa_scraper import build_output_filename, clean_text, parse_bopv_document


def test_parse_bopv_document_extracts_core_fields(sample_bopv_html: str) -> None:
    document = parse_bopv_document(
        sample_bopv_html,
        "https://www.euskadi.eus/bopv2/datos/2024/01/15/00012345.shtml",
        "es",
    )
    assert "Decreto" in document["title"]
    assert document["date_published"] == "2024-01-15"
    assert document["section"] == "I - DISPOSICIONES GENERALES"
    assert document["bopv_number"] == "00012345"
    assert len(document["paragraphs"]) >= 1


def test_clean_text_collapses_spaces() -> None:
    assert clean_text("  hola   mundo  ") == "hola mundo"


def test_build_output_filename() -> None:
    filename = build_output_filename(
        {"date_published": "2024-01-15", "document_id": "00012345", "language": "eu"}
    )
    assert filename == "ehaa_bopv_2024-01-15_00012345_eu.json"
