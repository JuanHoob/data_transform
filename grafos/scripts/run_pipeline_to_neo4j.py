#!/usr/bin/env python3
"""Pipeline automatizado para transformar JSON a CSV y cargarlo en Neo4j."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
JSON_TO_GRAPH_SCRIPT = Path(__file__).resolve().parent / "json_to_graph.py"
DEFAULT_CSV_OUTPUT_DIR = REPO_ROOT / "grafos" / "datos_grafos"
DEFAULT_PIPELINE_IMPORT_SUBDIR = "data_transform"


@dataclass(frozen=True)
class Neo4jConfig:
    csv_output_dir: Path
    import_dir: Path
    cypher_shell_path: Path
    username: str
    password: str
    node_label: str = "DataNode"
    relationship_type: str = "TIENE"
    import_subdir: str = DEFAULT_PIPELINE_IMPORT_SUBDIR
    neo4j_uri: str | None = None
    database: str | None = None

    @property
    def pipeline_import_dir(self) -> Path:
        return self.import_dir / self.import_subdir

    def cypher_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["NEO4J_USERNAME"] = self.username
        env["NEO4J_PASSWORD"] = self.password
        if self.neo4j_uri:
            env["NEO4J_URI"] = self.neo4j_uri
            env["NEO4J_ADDRESS"] = self.neo4j_uri
        if self.database:
            env["NEO4J_DATABASE"] = self.database
        return env


@dataclass(frozen=True)
class CsvPair:
    nodes_file: Path
    relationships_file: Path
    nodes_metadata: dict[str, Any]
    relationships_metadata: dict[str, Any]


def repo_relative(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def load_neo4j_config(
    env_file: Path | None = None, csv_output_dir: Path | None = None
) -> Neo4jConfig:
    """Carga y valida configuracion Neo4j solo cuando se ejecuta el pipeline."""
    env_path = env_file or REPO_ROOT / ".env"
    load_dotenv(env_path, verbose=False)

    password = os.getenv("NEO4J_PASSWORD")
    import_dir = os.getenv("NEO4J_IMPORT_DIR")
    cypher_shell_path = os.getenv("CYPHER_SHELL_PATH")

    missing = [
        name
        for name, value in {
            "NEO4J_PASSWORD": password,
            "NEO4J_IMPORT_DIR": import_dir,
            "CYPHER_SHELL_PATH": cypher_shell_path,
        }.items()
        if not value
    ]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Variables obligatorias no definidas: {joined}")

    configured_csv_dir = csv_output_dir or Path(os.getenv("CSV_OUTPUT_DIR", DEFAULT_CSV_OUTPUT_DIR))
    return Neo4jConfig(
        csv_output_dir=repo_relative(configured_csv_dir),
        import_dir=Path(import_dir),  # type: ignore[arg-type]
        cypher_shell_path=Path(cypher_shell_path),  # type: ignore[arg-type]
        username=os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME", "neo4j"),
        password=password or "",
        node_label=os.getenv("NEO4J_NODE_LABEL", "DataNode"),
        relationship_type=os.getenv("NEO4J_REL_TYPE", "TIENE"),
        import_subdir=os.getenv("NEO4J_IMPORT_SUBDIR", DEFAULT_PIPELINE_IMPORT_SUBDIR),
        neo4j_uri=os.getenv("NEO4J_URI") or os.getenv("NEO4J_ADDRESS"),
        database=os.getenv("NEO4J_DATABASE"),
    )


def discover_csv_files(csv_output_dir: Path) -> list[CsvPair]:
    """Descubre pares de archivos CSV y sus metadatos."""
    print("Descubriendo archivos CSV y metadatos...")
    pairs: list[CsvPair] = []
    nodes_files = sorted(csv_output_dir.glob("*_nodes.csv"))

    for nodes_file in nodes_files:
        base_name = nodes_file.stem.replace("_nodes", "")
        relationships_file = csv_output_dir / f"{base_name}_relationships.csv"
        if not relationships_file.exists():
            continue

        nodes_meta_file = nodes_file.with_suffix(".csv.metadata.json")
        relationships_meta_file = relationships_file.with_suffix(".csv.metadata.json")
        nodes_metadata = load_json_metadata(nodes_meta_file)
        relationships_metadata = load_json_metadata(relationships_meta_file)
        pairs.append(
            CsvPair(nodes_file, relationships_file, nodes_metadata, relationships_metadata)
        )
        print(f"  OK: {nodes_file.name} + {relationships_file.name}")

    print(f"\nTotal: {len(pairs)} pares\n")
    return pairs


def load_json_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def run_json_to_csv(config: Neo4jConfig, dry_run: bool = False) -> int:
    """Ejecuta json_to_graph.py para generar CSVs."""
    print("=" * 60)
    print("PASO 1: Generacion de CSVs")
    print("=" * 60)
    cmd = [sys.executable, str(JSON_TO_GRAPH_SCRIPT)]
    if dry_run:
        print(f"[DRY-RUN] Ejecutaria: {' '.join(cmd)}")
        return 0

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, check=False)
    print(result.stdout)
    if result.returncode != 0:
        print("Error al ejecutar json_to_graph.py")
        print(result.stderr)
    return result.returncode


def list_pipeline_csvs(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(path for path in directory.iterdir() if path.is_file() and path.suffix == ".csv")


def ensure_safe_pipeline_dir(config: Neo4jConfig) -> Path:
    target_dir = config.pipeline_import_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    resolved_import_dir = config.import_dir.resolve(strict=False)
    resolved_target_dir = target_dir.resolve(strict=False)
    if not resolved_target_dir.is_relative_to(resolved_import_dir):
        raise ValueError(f"Directorio import inseguro: {resolved_target_dir}")
    return target_dir


def copy_csv_to_import(
    csv_pairs: list[CsvPair], config: Neo4jConfig, dry_run: bool = False
) -> None:
    """Copia archivos CSV al subdirectorio dedicado del import de Neo4j."""
    print("=" * 60)
    print("PASO 2: Copia a Neo4j import/data_transform")
    print("=" * 60)

    target_dir = ensure_safe_pipeline_dir(config)
    old_csvs = list_pipeline_csvs(target_dir)
    for old_csv in old_csvs:
        if dry_run:
            print(f"[DRY-RUN] Borraria CSV previo: {old_csv}")
        else:
            old_csv.unlink()
            print(f"  Eliminado CSV previo: {old_csv.name}")

    for pair in csv_pairs:
        for source in (pair.nodes_file, pair.relationships_file):
            destination = target_dir / source.name
            if dry_run:
                print(f"[DRY-RUN] Copiaria: {source} -> {destination}")
            else:
                shutil.copy2(source, destination)
                print(f"  Copiado: {source.name}")
    print()


def csv_file_url(filename: str, config: Neo4jConfig) -> str:
    path = PurePosixPath(config.import_subdir) / filename
    return f"file:///{path.as_posix()}"


def cypher_shell_command(config: Neo4jConfig, plain: bool = False) -> list[str]:
    cmd = [str(config.cypher_shell_path)]
    if plain:
        cmd.extend(["--format", "plain"])
    return cmd


def run_cypher(config: Neo4jConfig, cypher: str, plain: bool = False, dry_run: bool = False) -> str:
    cmd = cypher_shell_command(config, plain=plain)
    if dry_run:
        print(f"[DRY-RUN] Ejecutaria cypher-shell: {' '.join(cmd)}")
        print(cypher)
        return ""

    result = subprocess.run(
        cmd,
        input=cypher,
        capture_output=True,
        text=True,
        env=config.cypher_env(),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout


def create_indexes(config: Neo4jConfig, dry_run: bool = False) -> None:
    """Crea indices y constraints en Neo4j."""
    print("=" * 60)
    print("PASO 3: Creacion de indices")
    print("=" * 60)
    cypher_commands = [
        (
            f"CREATE CONSTRAINT node_id_unique IF NOT EXISTS "
            f"FOR (n:{config.node_label}) REQUIRE n.id IS UNIQUE;"
        ),
        f"CREATE INDEX node_source_idx IF NOT EXISTS FOR (n:{config.node_label}) ON (n.source);",
        f"CREATE INDEX node_type_idx IF NOT EXISTS FOR (n:{config.node_label}) ON (n.type);",
    ]

    for command in cypher_commands:
        try:
            run_cypher(config, command, dry_run=dry_run)
        except RuntimeError as exc:
            print(f"  Error ejecutando comando Cypher:\n{exc}")
    print("Indices creados\n")


def load_csv_pair(pair: CsvPair, config: Neo4jConfig, dry_run: bool = False) -> bool:
    """Carga un par de CSVs (nodos y relaciones) en Neo4j."""
    source_name = pair.nodes_file.stem.replace("_nodes", "")
    print(f"Importando: {source_name}")

    nodes_url = csv_file_url(pair.nodes_file.name, config)
    rels_url = csv_file_url(pair.relationships_file.name, config)
    nodes_cypher = f"""USING PERIODIC COMMIT 5000
LOAD CSV WITH HEADERS FROM '{nodes_url}' AS row
MERGE (n:{config.node_label} {{id: row.id}})
SET n.name = row.name,
    n.label = row.label,
    n.source = row.source,
    n.type = row.type,
    n.path = row.path,
    n.depth = toInteger(row.depth),
    n.length = CASE
        WHEN row.length IS NOT NULL AND row.length <> '' THEN toInteger(row.length)
        ELSE null
    END,
    n.properties = row.properties;"""

    rels_cypher = f"""USING PERIODIC COMMIT 5000
LOAD CSV WITH HEADERS FROM '{rels_url}' AS row
MATCH (a:{config.node_label} {{id: row.start_id}})
MATCH (b:{config.node_label} {{id: row.end_id}})
MERGE (a)-[r:{config.relationship_type}]->(b)
SET r.original_type = row.type,
    r.properties = row.properties;"""

    try:
        run_cypher(config, nodes_cypher, dry_run=dry_run)
        print("  Nodos cargados")
        run_cypher(config, rels_cypher, dry_run=dry_run)
        print("  Relaciones cargadas\n")
    except RuntimeError as exc:
        print(f"  Error al cargar {source_name}:\n{exc}")
        return False
    return True


def parse_plain_count(output: str) -> int:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    for line in reversed(lines):
        try:
            return int(line)
        except ValueError:
            continue
    return 0


def verify_import_consistency(
    csv_pairs: list[CsvPair], config: Neo4jConfig, dry_run: bool = False
) -> bool:
    """Verifica consistencia de importacion comparando metadatos con Neo4j."""
    print("=" * 60)
    print("PASO 5: Verificacion de consistencia")
    print("=" * 60 + "\n")
    expected_nodes = sum(pair.nodes_metadata.get("total_nodes", 0) for pair in csv_pairs)
    expected_rels = sum(
        pair.relationships_metadata.get("total_relationships", 0) for pair in csv_pairs
    )
    print("Esperados (metadatos):")
    print(f"  Nodos: {expected_nodes:,}")
    print(f"  Relaciones: {expected_rels:,}\n")

    if dry_run:
        run_cypher(
            config,
            f"MATCH (n:{config.node_label}) RETURN count(n) AS total;",
            plain=True,
            dry_run=True,
        )
        run_cypher(
            config,
            f"MATCH ()-[r:{config.relationship_type}]->() RETURN count(r) AS total;",
            plain=True,
            dry_run=True,
        )
        return True

    actual_nodes = parse_plain_count(
        run_cypher(config, f"MATCH (n:{config.node_label}) RETURN count(n) AS total;", plain=True)
    )
    actual_rels = parse_plain_count(
        run_cypher(
            config,
            f"MATCH ()-[r:{config.relationship_type}]->() RETURN count(r) AS total;",
            plain=True,
        )
    )

    print("Importados (Neo4j):")
    print(f"  Nodos: {actual_nodes:,}")
    print(f"  Relaciones: {actual_rels:,}\n")

    nodes_deviation = (
        abs(actual_nodes - expected_nodes) / expected_nodes * 100 if expected_nodes else 0
    )
    rels_deviation = abs(actual_rels - expected_rels) / expected_rels * 100 if expected_rels else 0
    threshold = 2.0
    has_warnings = False

    if nodes_deviation > threshold:
        print(f"ADVERTENCIA: Desviacion en nodos: {nodes_deviation:.2f}%")
        has_warnings = True
    else:
        print(f"Nodos: Desviacion {nodes_deviation:.2f}% (OK)")

    if rels_deviation > threshold:
        print(f"ADVERTENCIA: Desviacion en relaciones: {rels_deviation:.2f}%")
        has_warnings = True
    else:
        print(f"Relaciones: Desviacion {rels_deviation:.2f}% (OK)")

    print()
    return not has_warnings


def run_neo4j_import(csv_pairs: list[CsvPair], config: Neo4jConfig, dry_run: bool = False) -> bool:
    """Importa todos los pares de CSVs a Neo4j."""
    print("=" * 60)
    print("PASO 4: Importacion a Neo4j")
    print("=" * 60 + "\n")
    create_indexes(config, dry_run=dry_run)

    success_count = 0
    for pair in csv_pairs:
        if load_csv_pair(pair, config, dry_run=dry_run):
            success_count += 1

    print("=" * 60)
    print(f"Importacion completada: {success_count}/{len(csv_pairs)} pares")
    print("=" * 60 + "\n")
    return verify_import_consistency(csv_pairs, config, dry_run=dry_run)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pipeline JSON -> CSV -> Neo4j")
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env", help="Ruta al .env")
    parser.add_argument("--csv-output-dir", type=Path, default=None, help="Directorio de CSVs")
    parser.add_argument("--dry-run", action="store_true", help="Muestra acciones sin ejecutarlas")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Ejecuta el pipeline completo."""
    args = build_arg_parser().parse_args(argv)
    try:
        config = load_neo4j_config(env_file=args.env_file, csv_output_dir=args.csv_output_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("\n" + "=" * 60)
    print("PIPELINE: JSON -> CSV -> Neo4j")
    print("=" * 60 + "\n")

    csv_pairs = discover_csv_files(config.csv_output_dir)
    if not csv_pairs:
        print("No se encontraron CSVs existentes. Generando...")
        result = run_json_to_csv(config, dry_run=args.dry_run)
        if result != 0:
            return result
        csv_pairs = discover_csv_files(config.csv_output_dir)
    else:
        print(f"Usando {len(csv_pairs)} pares de CSVs existentes")
        print("=" * 60 + "\n")

    if not csv_pairs:
        print("No se encontraron pares CSV")
        return 1

    copy_csv_to_import(csv_pairs, config, dry_run=args.dry_run)
    ok = run_neo4j_import(csv_pairs, config, dry_run=args.dry_run)
    print("\nPIPELINE FINALIZADO\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
