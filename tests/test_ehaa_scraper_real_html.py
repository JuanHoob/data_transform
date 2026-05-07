from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.euskorpus.ehaa_scraper import (
    build_output_filename,
    get_parallel_language_url,
    infer_bopv_language_from_url,
    is_bopv_document_url,
    is_bopv_summary_url,
    normalize_bopv_url,
    parse_bopv_document,
    parse_bopv_summary,
)

DATA_DIR = Path(__file__).parent / "data"
DOC_ES_URL = "https://www.euskadi.eus/bopv2/datos/2024/10/2404929a.shtml"
DOC_EU_URL = "https://www.euskadi.eus/bopv2/datos/2024/10/2404929e.shtml"
SUMMARY_URL = "https://www.euskadi.eus/bopv2/datos/2024/10/s24_0210.shtml"


def _read_fixture(name: str) -> str:
    return (DATA_DIR / name).read_text(encoding="utf-8")


def test_parse_real_bopv_document_extracts_metadata() -> None:
    document = parse_bopv_document(_read_fixture("bopv_2024_10_2404929a.html"), DOC_ES_URL)

    assert document["document_id"] == "2404929"
    assert document["language"] == "es"
    assert document["parallel_url"] == DOC_EU_URL
    assert document["title"]
    assert "Premios a la Protección de Datos" in document["title"]
    assert document["date_published"] == "2024-10-28"
    assert document["section"] == "OTRAS DISPOSICIONES"
    assert document["bopv_number"] == "210"
    assert document["order"] == "4929"


def test_parse_real_bopv_document_extracts_paragraphs_without_navigation() -> None:
    document = parse_bopv_document(_read_fixture("bopv_2024_10_2404929a.html"), DOC_ES_URL)
    texts = [paragraph["text"] for paragraph in document["paragraphs"]]

    assert len(texts) > 10
    assert any("Reglamento General de Protección de Datos" in text for text in texts)
    assert all("Mapa web" not in text for text in texts)
    assert all("Accesibilidad" not in text for text in texts)
    assert all("Sede Electrónica" not in text for text in texts)
    assert all("Solicitar una publicación" not in text for text in texts)


def test_detect_document_url_pattern() -> None:
    assert is_bopv_document_url(DOC_ES_URL)
    assert is_bopv_document_url(DOC_EU_URL)
    assert infer_bopv_language_from_url(DOC_ES_URL) == "es"
    assert infer_bopv_language_from_url(DOC_EU_URL) == "eu"
    assert normalize_bopv_url(
        "https://www.euskadi.eus/web01-bopv/es/bopv2/datos/2024/10/2404929a.shtml"
    ) == DOC_ES_URL


def test_detect_summary_url_pattern() -> None:
    assert is_bopv_summary_url(SUMMARY_URL)
    assert is_bopv_summary_url("https://www.euskadi.eus/web01-bopv/es/bopv2/datos/Ultimo.shtml")


def test_build_parallel_language_url_from_spanish() -> None:
    assert get_parallel_language_url(DOC_ES_URL) == DOC_EU_URL


def test_build_parallel_language_url_from_basque() -> None:
    assert get_parallel_language_url(DOC_EU_URL) == DOC_ES_URL


def test_parse_real_summary_extracts_document_links() -> None:
    links = parse_bopv_summary(_read_fixture("bopv_2024_10_s24_0210.html"), SUMMARY_URL)

    assert len(links) >= 30
    assert links[0].url.endswith("2404925a.shtml")
    assert any(link.document_id == "2404929" for link in links)
    matching = next(link for link in links if link.document_id == "2404929")
    assert matching.language == "es"
    assert matching.section_hint == "OTRAS DISPOSICIONES"
    assert matching.title_hint


def test_parse_real_basque_document_extracts_language_and_parallel() -> None:
    document = parse_bopv_document(_read_fixture("bopv_2024_10_2404929e.html"), DOC_EU_URL)

    assert document["document_id"] == "2404929"
    assert document["language"] == "eu"
    assert document["parallel_url"] == DOC_ES_URL
    assert document["date_published"] == "2024-10-28"
    assert document["bopv_number"] == "210"
    assert len(document["paragraphs"]) > 10


def test_build_output_filename_is_stable() -> None:
    document = {
        "date_published": "2024-10-28",
        "document_id": "2404929",
        "language": "es",
    }

    assert build_output_filename(document) == "ehaa_bopv_2024-10-28_2404929_es.json"


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("EUSKORPUS_RUN_LIVE_TESTS") != "1",
    reason="set EUSKORPUS_RUN_LIVE_TESTS=1 to run live BOPV tests",
)
def test_live_bopv_single_url() -> None:
    from scripts.euskorpus.ehaa_scraper import RateLimitedSession, scrape_document

    document = scrape_document(DOC_ES_URL, RateLimitedSession(rate_limit=0.1))

    assert document is not None
    assert document["document_id"] == "2404929"
    assert document["title"]
