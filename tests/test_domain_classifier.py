from __future__ import annotations

from scripts.euskorpus.domain_classifier import classify_document, classify_domain


def test_classify_domain_health() -> None:
    text = (
        "El decreto regula la prestacion sanitaria y los servicios de salud en los hospitales. "
        "Los pacientes tienen derecho a recibir tratamiento medico adecuado. "
        "La vacunacion es obligatoria segun la normativa sanitaria vigente."
    )
    assert classify_domain(text)["domain"] == "health"


def test_classify_domain_education() -> None:
    text = (
        "La ley de educacion establece el curriculo para la ensenanza primaria y secundaria. "
        "Los alumnos y profesores deben cumplir con los requisitos de titulacion. "
        "Las becas estan disponibles para estudios universitarios y formacion profesional."
    )
    assert classify_domain(text)["domain"] == "education"


def test_classify_domain_fiscal() -> None:
    text = (
        "El impuesto sobre la renta y el IVA se recaudan por la agencia tributaria. "
        "Los contribuyentes deben presentar la declaracion anual. "
        "Las deducciones fiscales y las exenciones tributarias estan reguladas por ley."
    )
    assert classify_domain(text)["domain"] == "fiscal"


def test_classify_document_adds_metadata() -> None:
    classified = classify_document({"paragraphs": ["La sanidad regula hospitales y pacientes."]})
    assert "domain_classification" in classified
    assert len(classified["domain_classification"]["paragraph_domains"]) == 1
