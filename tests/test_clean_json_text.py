from __future__ import annotations

from scripts.limpiezaD.clean_json_text import COMMON_MAP, clean_string, walk_and_clean


def test_clean_string_removes_private_use_and_maps_quotes() -> None:
    cleaned, metrics = clean_string("Hola\ue000 “mundo”", COMMON_MAP, {"\n", "\t"})
    assert cleaned == 'Hola "mundo"'
    assert metrics["chars_removed"] == 1
    assert metrics["chars_mapped"] == 2


def test_walk_and_clean_accumulates_metrics(sample_json_doc: dict) -> None:
    cleaned, metrics = walk_and_clean(sample_json_doc, False, set(), COMMON_MAP, {"\n", "\t"})
    assert cleaned["analyzeResult"]["paragraphs"][0]["content"]
    assert metrics["strings_total"] > 0
