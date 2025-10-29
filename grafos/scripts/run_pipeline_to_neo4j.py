#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pipeline automatizado para transformar JSON a CSV a Neo4j."""

import subprocess
import shutil
import sys
import json
from pathlib import Path

# Configuracion
JSON_TO_GRAPH_SCRIPT = Path(__file__).parent / "json_to_graph.py"
CSV_OUTPUT_DIR = Path(__file__).parent.parent / "datos_grafos"
NEO4J_IMPORT_DIR = Path(r"C:\Users\Juan\.Neo4jDesktop2\Data\dbmss\dbms-e27af981-1d2d-4852-8688-53edc0f4e59e\import")

NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "admin123"
CYPHER_SHELL_PATH = r"C:\Users\Juan\.Neo4jDesktop2\Cache\dbmss\neo4j-enterprise-2025.09.0\bin\cypher-shell.bat"

NODE_LABEL = "DataNode"
RELATIONSHIP_TYPE = "TIENE"


def discover_csv_files():
    """Descubre pares de archivos CSV y sus metadatos."""
    print("Descubriendo archivos CSV y metadatos...")
    pairs = []
    nodes_files = sorted(CSV_OUTPUT_DIR.glob("*_nodes.csv"))
    
    for nodes_file in nodes_files:
        base_name = nodes_file.stem.replace("_nodes", "")
        rels_file = CSV_OUTPUT_DIR / f"{base_name}_relationships.csv"
        
        if not rels_file.exists():
            continue
        
        nodes_meta_file = nodes_file.with_suffix(".csv.metadata.json")
        rels_meta_file = rels_file.with_suffix(".csv.metadata.json")
        
        nodes_metadata = {}
        rels_metadata = {}
        
        if nodes_meta_file.exists():
            with open(nodes_meta_file, "r", encoding="utf-8") as f:
                nodes_metadata = json.load(f)
        
        if rels_meta_file.exists():
            with open(rels_meta_file, "r", encoding="utf-8") as f:
                rels_metadata = json.load(f)
        
        pairs.append((nodes_file, rels_file, nodes_metadata, rels_metadata))
        print(f"  OK: {nodes_file.name} + {rels_file.name}")
    
    print(f"\nTotal: {len(pairs)} pares\n")
    return pairs


def run_json_to_csv():
    """Ejecuta json_to_graph.py para generar CSVs."""
    print("=" * 60)
    print("PASO 1: Generacion de CSVs")
    print("=" * 60)
    result = subprocess.run(
        [sys.executable, str(JSON_TO_GRAPH_SCRIPT)],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print("Error al ejecutar json_to_graph.py")
        print(result.stderr)
        sys.exit(1)


def copy_csv_to_import(csv_pairs):
    """Copia archivos CSV al directorio import de Neo4j."""
    print("=" * 60)
    print("PASO 2: Copia a Neo4j import")
    print("=" * 60)
    NEO4J_IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Limpiar CSVs antiguos para evitar conflictos
    for old_csv in NEO4J_IMPORT_DIR.glob("*.csv"):
        old_csv.unlink()
        print(f"  Eliminado CSV antiguo: {old_csv.name}")
    
    for nodes_file, rels_file, _, _ in csv_pairs:
        shutil.copy(nodes_file, NEO4J_IMPORT_DIR / nodes_file.name)
        shutil.copy(rels_file, NEO4J_IMPORT_DIR / rels_file.name)
        print(f"  Copiado: {nodes_file.name}")
    print()


def create_indexes():
    """Crea indices y constraints en Neo4j."""
    print("=" * 60)
    print("PASO 3: Creacion de indices")
    print("=" * 60)
    
    cypher_commands = [
        f"CREATE CONSTRAINT node_id_unique IF NOT EXISTS FOR (n:{NODE_LABEL}) REQUIRE n.id IS UNIQUE;",
        f"CREATE INDEX node_source_idx IF NOT EXISTS FOR (n:{NODE_LABEL}) ON (n.source);",
        f"CREATE INDEX node_type_idx IF NOT EXISTS FOR (n:{NODE_LABEL}) ON (n.type);",
    ]
    
    for cmd in cypher_commands:
        result = subprocess.run(
            [CYPHER_SHELL_PATH, "-u", NEO4J_USER, "-p", NEO4J_PASSWORD],
            input=cmd,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"  ⚠️  Error ejecutando comando Cypher:\n{result.stderr}")
    
    print("Indices creados\n")


def load_csv_pair(nodes_file, rels_file, nodes_meta, rels_meta):
    """Carga un par de CSVs (nodos y relaciones) en Neo4j."""
    source_name = nodes_file.stem.replace("_nodes", "")
    print(f"Importando: {source_name}")
    
    # Cargar nodos con todas las propiedades
    nodes_cypher = f"""USING PERIODIC COMMIT 5000
LOAD CSV WITH HEADERS FROM 'file:///{nodes_file.name}' AS row
MERGE (n:{NODE_LABEL} {{id: row.id}})
SET n.name = row.name,
    n.label = row.label,
    n.source = row.source,
    n.type = row.type,
    n.path = row.path,
    n.depth = toInteger(row.depth),
    n.length = CASE WHEN row.length IS NOT NULL AND row.length <> '' THEN toInteger(row.length) ELSE null END,
    n.properties = row.properties;"""
    
    result = subprocess.run(
        [CYPHER_SHELL_PATH, "-u", NEO4J_USER, "-p", NEO4J_PASSWORD],
        input=nodes_cypher,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"  ❌ Error al cargar nodos:\n{result.stderr}")
        return False
    print(f"  Nodos cargados")
    
    # Cargar relaciones
    rels_cypher = f"""USING PERIODIC COMMIT 5000
LOAD CSV WITH HEADERS FROM 'file:///{rels_file.name}' AS row
MATCH (a:{NODE_LABEL} {{id: row.start_id}})
MATCH (b:{NODE_LABEL} {{id: row.end_id}})
MERGE (a)-[r:{RELATIONSHIP_TYPE}]->(b)
SET r.original_type = row.type,
    r.properties = row.properties;"""
    
    result = subprocess.run(
        [CYPHER_SHELL_PATH, "-u", NEO4J_USER, "-p", NEO4J_PASSWORD],
        input=rels_cypher,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"  ❌ Error al cargar relaciones:\n{result.stderr}")
        return False
    print(f"  Relaciones cargadas\n")
    return True


def verify_import_consistency(csv_pairs):
    """Verifica la consistencia de la importación comparando metadatos con Neo4j."""
    print("=" * 60)
    print("PASO 5: Verificacion de consistencia")
    print("=" * 60 + "\n")
    
    # Calcular totales esperados desde metadatos
    expected_nodes = sum(meta[2].get('total_nodes', 0) for meta in csv_pairs)
    expected_rels = sum(meta[3].get('total_relationships', 0) for meta in csv_pairs)
    
    print(f"Esperados (metadatos):")
    print(f"  Nodos: {expected_nodes:,}")
    print(f"  Relaciones: {expected_rels:,}\n")
    
    # Consultar Neo4j para totales reales
    summary_query = f"""MATCH (n:{NODE_LABEL}) RETURN count(n) AS total;"""
    result = subprocess.run(
        [CYPHER_SHELL_PATH, "-u", NEO4J_USER, "-p", NEO4J_PASSWORD, "--format", "plain"],
        input=summary_query,
        capture_output=True,
        text=True
    )
    
    actual_nodes = 0
    if result.returncode == 0:
        # Extraer el número del output (formato: "total\n12345")
        lines = result.stdout.strip().split('\n')
        if len(lines) > 1:
            try:
                actual_nodes = int(lines[-1])
            except ValueError:
                pass
    
    summary_rels = f"""MATCH ()-[r:{RELATIONSHIP_TYPE}]->() RETURN count(r) AS total;"""
    result = subprocess.run(
        [CYPHER_SHELL_PATH, "-u", NEO4J_USER, "-p", NEO4J_PASSWORD, "--format", "plain"],
        input=summary_rels,
        capture_output=True,
        text=True
    )
    
    actual_rels = 0
    if result.returncode == 0:
        lines = result.stdout.strip().split('\n')
        if len(lines) > 1:
            try:
                actual_rels = int(lines[-1])
            except ValueError:
                pass
    
    print(f"Importados (Neo4j):")
    print(f"  Nodos: {actual_nodes:,}")
    print(f"  Relaciones: {actual_rels:,}\n")
    
    # Calcular desviaciones
    nodes_deviation = 0
    rels_deviation = 0
    
    if expected_nodes > 0:
        nodes_deviation = abs(actual_nodes - expected_nodes) / expected_nodes * 100
    
    if expected_rels > 0:
        rels_deviation = abs(actual_rels - expected_rels) / expected_rels * 100
    
    # Umbral de advertencia: 2%
    THRESHOLD = 2.0
    has_warnings = False
    
    if nodes_deviation > THRESHOLD:
        print(f"⚠️  ADVERTENCIA: Desviacion en nodos: {nodes_deviation:.2f}%")
        print(f"    Diferencia: {abs(actual_nodes - expected_nodes):,} nodos")
        has_warnings = True
    else:
        print(f"✅ Nodos: Desviacion {nodes_deviation:.2f}% (OK)")
    
    if rels_deviation > THRESHOLD:
        print(f"⚠️  ADVERTENCIA: Desviacion en relaciones: {rels_deviation:.2f}%")
        print(f"    Diferencia: {abs(actual_rels - expected_rels):,} relaciones")
        has_warnings = True
    else:
        print(f"✅ Relaciones: Desviacion {rels_deviation:.2f}% (OK)")
    
    print()
    return not has_warnings


def run_neo4j_import(csv_pairs):
    """Importa todos los pares de CSVs a Neo4j."""
    print("=" * 60)
    print("PASO 4: Importacion a Neo4j")
    print("=" * 60 + "\n")
    
    create_indexes()
    
    success_count = 0
    for nodes_file, rels_file, nodes_meta, rels_meta in csv_pairs:
        if load_csv_pair(nodes_file, rels_file, nodes_meta, rels_meta):
            success_count += 1
    
    print("=" * 60)
    print(f"Importacion completada: {success_count}/{len(csv_pairs)} pares")
    print("=" * 60 + "\n")
    
    # Verificar consistencia
    verify_import_consistency(csv_pairs)


def main():
    """Ejecuta el pipeline completo."""
    print("\n" + "=" * 60)
    print("PIPELINE: JSON -> CSV -> Neo4j")
    print("=" * 60 + "\n")
    
    # Descubrir archivos CSV existentes
    csv_pairs = discover_csv_files()
    
    # Solo generar CSVs si no existen
    if not csv_pairs:
        print("No se encontraron CSVs existentes. Generando...")
        run_json_to_csv()
        csv_pairs = discover_csv_files()
    else:
        print(f"Usando {len(csv_pairs)} pares de CSVs existentes")
        print("=" * 60 + "\n")
    
    if not csv_pairs:
        print("No se encontraron pares CSV")
        sys.exit(1)
    
    copy_csv_to_import(csv_pairs)
    run_neo4j_import(csv_pairs)
    
    print("\nPIPELINE FINALIZADO\n")


if __name__ == "__main__":
    main()
