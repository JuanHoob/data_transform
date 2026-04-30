from __future__ import annotations

from scripts.euskorpus.lang_detect import annotate_document, detect_language


def test_detect_language_basque(sample_basque_text: str) -> None:
    result = detect_language(sample_basque_text)
    assert result["language"] == "eu"
    assert result["confidence"] > 0.55


def test_detect_language_spanish(sample_spanish_text: str) -> None:
    result = detect_language(sample_spanish_text)
    assert result["language"] == "es"


def test_detect_language_short_text_unknown() -> None:
    result = detect_language("Kaixo")
    assert result["language"] == "unknown"


def test_annotate_document_adds_paragraph_annotations(
    sample_basque_text: str, sample_spanish_text: str
) -> None:
    document = {"paragraphs": [sample_basque_text, sample_spanish_text, "Kaixo"]}
    annotated = annotate_document(document)
    assert "language_annotations" in annotated
    assert len(annotated["language_annotations"]["paragraphs"]) == 3
    assert annotated["language_annotations"]["dominant_language"] in {"eu", "es"}
