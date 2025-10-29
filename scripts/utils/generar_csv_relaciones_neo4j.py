#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Genera y/o fusiona el CSV de relaciones para Neo4j a partir de:
- Nodos existentes: grafos/datos_grafos/invikta_bbdd_nodes.csv
- Relaciones inferidas: data/json_schemas/*.relations.csv

Salida:
- grafos/datos_grafos/invikta_bbdd_relationships.csv  (start_id,end_id,type)
- (opcional) grafos/datos_grafos/invikta_bbdd_orphan_nodes.csv

Uso:
  python scripts/utils/generar_csv_relaciones_neo4j.py --preview-nodes
  python scripts/utils/generar_csv_relaciones_neo4j.py --merge --allow-orphans --default-type TIENE
"""

import argparse
import glob
import os
import sys
import pandas as pd

# ----- Rutas por defecto (relativas al repo) -----
NODES_CSV = os.path.join("grafos", "datos_grafos", "invikta_bbdd_nodes.csv")
RELATIONS_GLOB = os.path.join("data", "json_schemas", "*.relations.csv")
REL_OUT = os.path.join("grafos", "datos_grafos", "invikta_bbdd_relationships.csv")
ORPHANS_OUT = os.path.join("grafos", "datos_grafos", "invikta_bbdd_orphan_nodes.csv")

REQUIRED_REL_COLS = {"parent_node", "child_node"}  # mínimas
POSSIBLE_REL_TYPE_COLS = ["type", "relation", "rel", "edge_type"]  # alias aceptados

# Tipos base de Azure DI que deben heredar el source del padre
BASE_TYPES = {"pages", "words", "lines", "spans", "paragraphs", "boundingRegions", "styles"}


def warn(msg: str):
    print(f"[WARN] {msg}", file=sys.stderr)


def info(msg: str):
    print(f"[INFO] {msg}")


def err(msg: str):
    print(f"[ERROR] {msg}", file=sys.stderr)


def load_nodes(nodes_csv: str) -> pd.DataFrame:
    if not os.path.isfile(nodes_csv):
        err(f"No existe el CSV de nodos: {nodes_csv}")
        sys.exit(2)
    df = pd.read_csv(nodes_csv, dtype=str).fillna("")
    # Normalizamos columnas clave si faltan
    for col in ["id", "name", "type", "source"]:
        if col not in df.columns:
            df[col] = ""
    # Limpieza básica
    df["id"] = df["id"].astype(str)
    df["name"] = df["name"].astype(str)
    df["type"] = df["type"].astype(str)
    df["source"] = df["source"].astype(str)
    return df


def canonical_key_from_row(row) -> str:
    """
    Clave canónica para match de nodos cuando no matchea id/name directos.
    Usa source + '_' + type si existen; si no, devuelve ''.
    """
    src = (row.get("source") or "").strip()
    typ = (row.get("type") or "").strip()
    if src and typ:
        return f"{src}_{typ}"
    return ""


def build_node_index(df_nodes: pd.DataFrame):
    """
    Construye índices de resolución:
    - por id
    - por name
    - por clave canónica (source_type)
    """
    id_map = {}
    name_map = {}
    canon_map = {}

    for _, r in df_nodes.iterrows():
        nid = r["id"].strip()
        nname = r["name"].strip()
        ckey = canonical_key_from_row(r)

        if nid:
            id_map.setdefault(nid, nid)
        if nname:
            name_map.setdefault(nname, nid)
        if ckey:
            canon_map.setdefault(ckey, nid)

    return id_map, name_map, canon_map


def find_rel_type_column(df_rel: pd.DataFrame) -> str:
    for c in POSSIBLE_REL_TYPE_COLS:
        if c in df_rel.columns:
            return c
    return ""  # no hay columna de tipo


def resolve_node_id(token: str, id_map, name_map, canon_map) -> str:
    """
    Intenta resolver un identificador de nodo a su id final.
    Orden:
      1) id exacto
      2) name exacto
      3) clave canónica (cuando el token ya viene con patrón source_type)
    """
    t = (token or "").strip()
    if not t:
        return ""

    # 1) ¿es un id existente?
    if t in id_map:
        return id_map[t]

    # 2) ¿coincide con name?
    if t in name_map:
        return name_map[t]

    # 3) ¿parece ya un patrón source_type? (heurística simple: contiene '_')
    if "_" in t and t in canon_map:
        return canon_map[t]

    # No resuelto
    return ""


def load_all_relations(rel_glob: str) -> pd.DataFrame:
    files = sorted(glob.glob(rel_glob))
    if not files:
        warn(f"No se encontraron .relations.csv en: {rel_glob}")
        return pd.DataFrame(columns=["parent_node", "child_node", "type", "source_file"])

    frames = []
    for f in files:
        try:
            df = pd.read_csv(f, dtype=str).fillna("")
        except Exception as e:
            warn(f"No se pudo leer {f}: {e}")
            continue

        missing = REQUIRED_REL_COLS - set(df.columns)
        if missing:
            warn(f"Archivo {os.path.basename(f)} ignorado: faltan columnas {missing}")
            continue

        # Normaliza nombre de columna de tipo (si existe con otro alias)
        rcol = find_rel_type_column(df)
        if rcol and rcol != "type":
            df["type"] = df[rcol]
        elif "type" not in df.columns:
            df["type"] = ""

        df["source_file"] = os.path.basename(f)
        frames.append(df[["parent_node", "child_node", "type", "source_file"]])

    if not frames:
        return pd.DataFrame(columns=["parent_node", "child_node", "type", "source_file"])

    return pd.concat(frames, ignore_index=True)


def dedupe_edges(df_edges: pd.DataFrame) -> pd.DataFrame:
    # Elimina duplicados exactos por (start_id, end_id, type)
    return df_edges.drop_duplicates(subset=["start_id", "end_id", "type"], keep="first")


def main():
    ap = argparse.ArgumentParser(description="Genera relationships.csv para Neo4j desde *.relations.csv")
    ap.add_argument("--nodes", default=NODES_CSV, help="Ruta al CSV de nodos")
    ap.add_argument("--relations-glob", default=RELATIONS_GLOB, help="Patrón glob de relations CSV")
    ap.add_argument("--out", default=REL_OUT, help="Archivo de salida relationships")
    ap.add_argument("--orphans-out", default=ORPHANS_OUT, help="Archivo de salida de nodos huérfanos")
    ap.add_argument("--default-type", dest="default_type", default="TIENE", help="Tipo por defecto si falta")
    ap.add_argument("--merge", action="store_true", help="Fusionar con relationships existente")
    ap.add_argument("--allow-orphans", dest="allow_orphans", action="store_true", help="Permitir crear nodos huérfanos sintéticos")
    ap.add_argument("--preview-nodes", dest="preview_nodes", action="store_true", help="Sólo mostrar vista previa de IDs de nodos y salir")
    args = ap.parse_args()

    # 1) Cargar nodos y preparar índices
    df_nodes = load_nodes(args.nodes)
    id_map, name_map, canon_map = build_node_index(df_nodes)
    
    # Índice para ir del id de nodo a su fila (para recuperar 'source' y 'type')
    nodes_by_id = {row["id"]: row for _, row in df_nodes.iterrows()}
    
    def source_of(node_id: str) -> str:
        """Obtiene el 'source' del nodo si existe; si no, intenta inferirlo del prefijo del id."""
        row = nodes_by_id.get(node_id, {})
        src = (row.get("source") or "").strip()
        if src:
            return src
        # Heurística: muchos ids vienen como 'AirTAC-Booklet-EU-EN_pages' → 'AirTAC-Booklet-EU-EN'
        if "_" in node_id:
            return node_id.split("_", 1)[0]
        return ""

    if args.preview_nodes:
        info(f"Nodos cargados: {len(df_nodes)}")
        # Mostrar ejemplos útiles
        cols = [c for c in ["id", "name", "type", "source"] if c in df_nodes.columns]
        info("Vista previa de nodos (top 20):")
        print(df_nodes[cols].head(20).to_string(index=False))
        # También algunas claves canónicas no vacías
        df_nodes["_ckey"] = df_nodes.apply(canonical_key_from_row, axis=1)
        sample_ck = df_nodes[df_nodes["_ckey"] != ""][["_ckey", "id"]].head(20)
        if not sample_ck.empty:
            info("Claves canónicas detectadas (source_type) → id (top 20):")
            print(sample_ck.to_string(index=False))
        sys.exit(0)

    # 2) Cargar todas las relaciones
    df_rel = load_all_relations(args.relations_glob)
    if df_rel.empty:
        warn("No hay relaciones que procesar. Nada que hacer.")
        sys.exit(0)

    # 3) Resolver IDs
    out_rows = []
    orphan_rows = []  # para documentar huérfanos creados
    missing_pairs = 0

    for _, r in df_rel.iterrows():
        p_raw = r["parent_node"]
        c_raw = r["child_node"]
        etype = r.get("type", "").strip() or args.default_type

        start_id = resolve_node_id(p_raw, id_map, name_map, canon_map)
        end_id = resolve_node_id(c_raw, id_map, name_map, canon_map)

        # Si no se resuelve el hijo y es un tipo base, intentar con source del padre
        if not end_id:
            # Si el hijo es un tipo base 'pages/words/...' y el padre está resuelto, intenta canónico
            if c_raw in BASE_TYPES and start_id:
                parent_src = source_of(start_id)
                if parent_src:
                    candidate = f"{parent_src}_{c_raw}"
                    # ¿existe tal id?
                    cand_resolved = resolve_node_id(candidate, id_map, name_map, canon_map)
                    if cand_resolved:
                        end_id = cand_resolved
                    else:
                        # Si permitimos huérfanos, creamos el nodo *canónico* (no ORPHAN::)
                        if args.allow_orphans:
                            end_id = candidate
                            orphan_row = {
                                "id": end_id,
                                "name": c_raw,
                                "type": c_raw,        # etiqueta útil (p.ej. 'pages')
                                "source": parent_src  # clave para trazabilidad
                            }
                            orphan_rows.append(orphan_row)
                            # Registrar en índices para que pueda ser padre en siguientes iteraciones
                            id_map[end_id] = end_id
                            name_map[c_raw] = end_id
                            nodes_by_id[end_id] = orphan_row

        # Si no se resuelve alguno (y no es tipo base o no se pudo resolver con source):
        if not start_id or not end_id:
            if args.allow_orphans:
                if not start_id:
                    start_id = f"ORPHAN::{p_raw}"
                    orphan_row = {"id": start_id, "name": p_raw, "type": "orphan", "source": "relations"}
                    orphan_rows.append(orphan_row)
                    # Registrar también los orphans ORPHAN:: por si acaso
                    id_map[start_id] = start_id
                    nodes_by_id[start_id] = orphan_row
                if not end_id:
                    end_id = f"ORPHAN::{c_raw}"
                    orphan_row = {"id": end_id, "name": c_raw, "type": "orphan", "source": "relations"}
                    orphan_rows.append(orphan_row)
                    # Registrar también
                    id_map[end_id] = end_id
                    nodes_by_id[end_id] = orphan_row
            else:
                missing_pairs += 1
                continue

        out_rows.append({"start_id": start_id, "end_id": end_id, "type": etype})

    df_out = pd.DataFrame(out_rows, columns=["start_id", "end_id", "type"])
    if df_out.empty:
        warn("No se generaron relaciones (¿todo falló por resolución de IDs?).")
        if missing_pairs:
            warn(f"Relaciones omitidas por no resolver IDs: {missing_pairs}")
        sys.exit(0)

    df_out = dedupe_edges(df_out)

    # 4) Merge con relationships existente si se pide
    if args.merge and os.path.isfile(args.out):
        try:
            df_prev = pd.read_csv(args.out, dtype=str).fillna("")
            if set(["start_id", "end_id", "type"]) <= set(df_prev.columns):
                df_merged = pd.concat([df_prev[["start_id", "end_id", "type"]], df_out], ignore_index=True)
                df_merged = dedupe_edges(df_merged)
                df_out = df_merged
                info(f"Merge realizado con {args.out}. Total relaciones: {len(df_out)}")
            else:
                warn(f"{args.out} existente no tiene columnas esperadas; se sobrescribirá.")
        except Exception as e:
            warn(f"No se pudo leer {args.out} para merge ({e}); se sobrescribe con nuevas relaciones.")

    # 5) Escribir relaciones
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df_out.to_csv(args.out, index=False)
    info(f"Escrito: {args.out} ({len(df_out)} relaciones).")

    # 6) Orphanos (opcional)
    if args.allow_orphans and orphan_rows:
        df_orph = pd.DataFrame(orphan_rows).drop_duplicates(subset=["id"])
        df_orph.to_csv(args.orphans_out, index=False)
        info(f"Registrados nodos huérfanos: {len(df_orph)} → {args.orphans_out}")

    if missing_pairs and not args.allow_orphans:
        warn(f"Relaciones omitidas por no resolver IDs (sin --allow-orphans): {missing_pairs}")

    # 7) Resumen
    # Muestra 10 relaciones de ejemplo para ver patrón
    info("Muestra (10) de relaciones resultantes:")
    print(df_out.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
