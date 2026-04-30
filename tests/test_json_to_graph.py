from __future__ import annotations

from grafos.scripts.json_to_graph import traverse_json


def test_traverse_json_stores_primitives_as_properties() -> None:
    test_obj = {
        "titulo": "Decreto de prueba",
        "anio": 2024,
        "activo": True,
        "tags": ["legal", "eu"],
        "sub": {"clave": "valor"},
    }
    nodes = {}
    relationships = []
    seen = set()

    traverse_json(test_obj, "", "test_source", "", nodes, relationships, seen)

    root_node = next(node for node in nodes.values() if node.get("path") == "")
    assert root_node["prop_titulo"] == "Decreto de prueba"
    assert root_node["prop_anio"] == "2024"
    assert root_node["prop_activo"] == "True"
    assert root_node["prop_tags"] == "legal; eu"
    assert "prop_sub" not in root_node
