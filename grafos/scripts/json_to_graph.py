#!/usr/bin/env python3
"""
Script mejorado para transformar JSON limpios en nodos y relaciones CSV para Neo4j.
Genera nodos estructurales (dict/list) y almacena valores primitivos como propiedades.
Evita explosión de nodos innecesarios.
"""

import json
import csv
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple, Set
from collections import defaultdict
from datetime import datetime


# ---------- FUNCIONES BASE ----------

def sanitize_path(path: str) -> str:
    """
    Sanitiza el path para crear IDs seguros para Neo4j.
    Reemplaza caracteres problemáticos por guiones bajos.
    """
    if not path:
        return ""
    return (path
            .replace(".", "_")
            .replace("[", "_")
            .replace("]", "")
            .replace(" ", "_")
            .replace("-", "_")
            .replace("/", "_")
            .strip("_"))


def load_json_file(file_path: str) -> Dict[str, Any]:
    """Carga un archivo JSON con manejo de errores."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error al cargar {file_path}: {e}")
        return {}


def traverse_json(obj: Any, parent_id: str, source_file: str, path: str,
                  nodes: Dict[str, Dict[str, Any]], relationships: List[Dict[str, Any]],
                  seen_ids: Set[str], depth: int = 0, max_depth: int = 50):
    """
    Recorre recursivamente el JSON generando nodos solo para estructuras (dict/list).
    Los valores primitivos se almacenan como propiedades del nodo padre.
    
    Args:
        obj: Objeto JSON actual
        parent_id: ID del nodo padre
        source_file: Nombre del archivo de origen
        path: Ruta JSON completa (para IDs únicos)
        nodes: Dict de nodos (clave: id, valor: dict de propiedades)
        relationships: Lista de relaciones
        seen_ids: Set de IDs ya procesados para evitar duplicados
        depth: Profundidad actual de recursión
        max_depth: Profundidad máxima permitida (evita recursión infinita)
    """
    # Protección contra recursión excesiva
    if depth > max_depth:
        print(f"  ⚠️  Profundidad máxima alcanzada ({max_depth}) en path: {path}")
        return
    
    if isinstance(obj, dict):
        # Crear nodo para el diccionario
        safe_path = sanitize_path(path) if path else "root"
        node_id = f"{source_file}_{safe_path}"
        
        if node_id not in seen_ids:
            seen_ids.add(node_id)
            node = {
                "id": node_id,
                "label": "ObjectNode",
                "name": path.split(".")[-1] if path else source_file,
                "source": source_file,
                "type": "dict",
                "path": path,
                "depth": str(depth)
            }
            
            # Agregar valores primitivos como propiedades
            primitive_props = {}
            for key, value in obj.items():
                if isinstance(value, (str, int, float, bool, type(None))):
                    primitive_props[key] = str(value) if value is not None else ""
            
            if primitive_props:
                node["properties"] = json.dumps(primitive_props, ensure_ascii=False)
            
            nodes[node_id] = node

            if parent_id and parent_id != node_id:
                relationships.append({
                    "start_id": parent_id,
                    "end_id": node_id,
                    "type": "TIENE",
                    "properties": ""
                })

        # Recorrer hijos que sean estructuras
        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                child_path = f"{path}.{key}" if path else key
                traverse_json(value, node_id, source_file, child_path, nodes, relationships, seen_ids, depth + 1, max_depth)

    elif isinstance(obj, list):
        # Para listas: solo crear nodos si contienen estructuras complejas
        has_structures = any(isinstance(item, (dict, list)) for item in obj)
        
        if has_structures:
            # Crear nodo para la lista
            safe_path = sanitize_path(path)
            list_node_id = f"{source_file}_{safe_path}"
            
            if list_node_id not in seen_ids:
                seen_ids.add(list_node_id)
                nodes[list_node_id] = {
                    "id": list_node_id,
                    "label": "ArrayNode",
                    "name": path.split(".")[-1] if path else "array",
                    "source": source_file,
                    "type": "list",
                    "path": path,
                    "length": str(len(obj)),
                    "depth": str(depth)
                }
                
                if parent_id and parent_id != list_node_id:
                    relationships.append({
                        "start_id": parent_id,
                        "end_id": list_node_id,
                        "type": "TIENE",
                        "properties": ""
                    })
            
            # Procesar items que sean estructuras
            for i, item in enumerate(obj):
                if isinstance(item, (dict, list)):
                    item_path = f"{path}[{i}]"
                    traverse_json(item, list_node_id, source_file, item_path, nodes, relationships, seen_ids, depth + 1, max_depth)
        else:
            # Lista de primitivos: guardar como propiedad en el padre si existe
            if parent_id and parent_id in nodes:
                prop_key = path.split(".")[-1] if "." in path else path
                if "properties" not in nodes[parent_id]:
                    nodes[parent_id]["properties"] = "{}"
                
                props = json.loads(nodes[parent_id]["properties"]) if nodes[parent_id].get("properties") else {}
                props[prop_key] = json.dumps(obj, ensure_ascii=False)
                nodes[parent_id]["properties"] = json.dumps(props, ensure_ascii=False)


def extract_nodes_and_relationships(data: Dict[str, Any], source_file: str, max_depth: int = 50) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Extrae nodos estructurales y relaciones de un JSON.
    Evita crear nodos para valores primitivos (se almacenan como propiedades).
    
    Args:
        data: Datos JSON a procesar
        source_file: Nombre del archivo de origen
        max_depth: Profundidad máxima de recursión permitida
    """
    nodes_dict = {}  # Usar dict para deduplicación automática
    relationships = []
    seen_ids = set()

    # Nodo raíz del documento
    root_id = f"{source_file}_root"
    seen_ids.add(root_id)
    nodes_dict[root_id] = {
        "id": root_id,
        "label": "DocumentRoot",
        "name": source_file,
        "source": source_file,
        "type": "root",
        "path": "",
        "depth": "0"
    }

    traverse_json(data, root_id, source_file, "", nodes_dict, relationships, seen_ids, 0, max_depth)
    
    return list(nodes_dict.values()), relationships


def write_nodes_csv(nodes: List[Dict[str, Any]], filepath: Path):
    """Escribe los nodos en CSV con todas las columnas detectadas."""
    if not nodes:
        print("  ⚠️  No hay nodos para escribir")
        return
    
    # Detectar todas las claves únicas en los nodos
    all_keys = set()
    for node in nodes:
        all_keys.update(node.keys())
    
    fieldnames = ["id", "label", "name", "source", "type", "path", "depth"]
    # Agregar columnas adicionales al final
    for key in sorted(all_keys):
        if key not in fieldnames:
            fieldnames.append(key)
    
    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(nodes)
    
    # Escribir metadatos en archivo JSON separado (CSV-lint compatible)
    metadata_path = filepath.with_suffix('.metadata.json')
    metadata = {
        "generated_by": Path(__file__).name,
        "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "total_nodes": len(nodes),
        "columns": fieldnames,
        "file_type": "nodes",
        "csv_file": filepath.name
    }
    with open(metadata_path, 'w', encoding='utf-8') as metafile:
        json.dump(metadata, metafile, indent=2, ensure_ascii=False)
    
    print(f"  📄 Nodos escritos: {len(nodes)}")


def write_relationships_csv(relationships: List[Dict[str, Any]], filepath: Path):
    """Escribe las relaciones en CSV."""
    if not relationships:
        print("  ⚠️  No hay relaciones para escribir")
        return
    
    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ["start_id", "end_id", "type", "properties"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(relationships)
    
    # Escribir metadatos en archivo JSON separado (CSV-lint compatible)
    metadata_path = filepath.with_suffix('.metadata.json')
    
    # Contar tipos de relaciones
    rel_types = {}
    for rel in relationships:
        rel_type = rel.get("type", "UNKNOWN")
        rel_types[rel_type] = rel_types.get(rel_type, 0) + 1
    
    metadata = {
        "generated_by": Path(__file__).name,
        "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "total_relationships": len(relationships),
        "relationship_types": rel_types,
        "file_type": "relationships",
        "csv_file": filepath.name
    }
    with open(metadata_path, 'w', encoding='utf-8') as metafile:
        json.dump(metadata, metafile, indent=2, ensure_ascii=False)
    
    print(f"  🔗 Relaciones escritas: {len(relationships)}")


def process_json_files(input_dir: str, output_dir: str, max_depth: int = 50):
    """
    Procesa todos los archivos JSON de un directorio.
    
    Args:
        input_dir: Directorio de entrada con archivos JSON
        output_dir: Directorio de salida para CSV
        max_depth: Profundidad máxima de recursión
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    if not input_path.exists():
        print(f"❌ El directorio {input_dir} no existe.")
        return

    output_path.mkdir(parents=True, exist_ok=True)
    
    total_nodes = 0
    total_rels = 0
    processed_files = 0

    for json_file in sorted(input_path.glob("*.json")):
        print(f"\n▶ Procesando {json_file.name}...")
        data = load_json_file(str(json_file))
        if not data:
            continue

        nodes, relationships = extract_nodes_and_relationships(data, json_file.stem, max_depth)
        nodes_file = output_path / f"{json_file.stem}_nodes.csv"
        rels_file = output_path / f"{json_file.stem}_relationships.csv"

        write_nodes_csv(nodes, nodes_file)
        write_relationships_csv(relationships, rels_file)
        
        total_nodes += len(nodes)
        total_rels += len(relationships)
        processed_files += 1

        print(f"✅ Generados: {nodes_file.name}, {rels_file.name}")
    
    print(f"\n{'='*60}")
    print(f"🎉 Transformación completada:")
    print(f"   📁 Archivos procesados: {processed_files}")
    print(f"   📦 Total nodos: {total_nodes}")
    print(f"   🔗 Total relaciones: {total_rels}")
    print(f"   🔢 Profundidad máxima: {max_depth}")
    print(f"{'='*60}")


def main():
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(
        description="Transforma archivos JSON a nodos y relaciones CSV para Neo4j",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  %(prog)s
  %(prog)s /ruta/entrada /ruta/salida
  %(prog)s --max-depth 30
  %(prog)s /ruta/entrada /ruta/salida --max-depth 20
        """
    )
    parser.add_argument("input_dir", nargs="?", help="Directorio con archivos JSON de entrada")
    parser.add_argument("output_dir", nargs="?", help="Directorio para archivos CSV de salida")
    parser.add_argument("--max-depth", type=int, default=50, 
                        help="Profundidad máxima de recursión (default: 50)")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔄 JSON to Neo4j Graph Converter")
    print("=" * 60)
    
    if args.input_dir and args.output_dir:
        input_dir = args.input_dir
        output_dir = args.output_dir
        print(f"📂 Entrada: {input_dir}")
        print(f"📂 Salida: {output_dir}")
    else:
        base_dir = Path(__file__).parent.parent.parent  # asume estructura data_transform/
        input_dir = str(base_dir / "data" / "limpios_json")
        output_dir = str(base_dir / "grafos" / "datos_grafos")
        print(f"📂 Usando rutas por defecto:")
        print(f"   Entrada: {input_dir}")
        print(f"   Salida: {output_dir}")
    
    print(f"🔢 Profundidad máxima: {args.max_depth}")

    process_json_files(input_dir, output_dir, args.max_depth)


if __name__ == "__main__":
    main()
