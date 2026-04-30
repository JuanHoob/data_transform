from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def sample_bopv_html() -> str:
    return (DATA_DIR / "sample_bopv.html").read_text(encoding="utf-8")


@pytest.fixture
def sample_basque_text() -> str:
    return (
        "Hezkuntza sailak ikastetxeetan aplikatzeko araudia onartu du, "
        "eta ikasleek eta irakasleek onartutako xedapenak bete behar dituzte. "
        "Lege hau indarrean sartu zen eta erkidegoaren hezkuntza sisteman garrantzitsua da."
    )


@pytest.fixture
def sample_spanish_text() -> str:
    return (
        "El decreto establece los requisitos para la prestacion de servicios sanitarios "
        "en los centros hospitalarios de la Comunidad Autonoma. La ley regula la normativa "
        "juridica y las disposiciones legales aplicables al territorio."
    )


@pytest.fixture
def sample_json_doc() -> dict:
    return json.loads((DATA_DIR / "sample_doc.json").read_text(encoding="utf-8"))


@pytest.fixture
def tmp_corpus_dir(tmp_path: Path) -> Path:
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    return corpus_dir
