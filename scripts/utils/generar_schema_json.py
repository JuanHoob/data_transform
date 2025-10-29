import json
from pathlib import Path
from genson import SchemaBuilder
import csv


def infer_relationships(data, parent_key=None, parent_path=None, results=None):
    """Detecta relaciones padre-hijo en estructuras anidadas tipo list[dict]."""
    if results is None:
        results = []
    if isinstance(data, dict):
        for k, v in data.items():
            current_path = f"{parent_path}.{k}" if parent_path else k
            if isinstance(v, list) and all(isinstance(i, dict) for i in v):
                results.append((parent_key or "ROOT", k, current_path))
                for i in v:
                    infer_relationships(i, k, current_path, results)
            elif isinstance(v, dict):
                infer_relationships(v, k, current_path, results)
    return results


def generar_schemas(input_dir: Path, output_dir: Path):
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    for json_file in input_dir.glob("*.json"):
        print(f"🧩 Procesando: {json_file.name}")
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ Error al leer {json_file.name}: {e}")
            continue

        # Generar esquema JSON
        builder = SchemaBuilder()
        builder.add_object(data)

        schema_path = output_dir / f"{json_file.stem}.schema.json"
        with open(schema_path, "w", encoding="utf-8") as f_out:
            json.dump(builder.to_schema(), f_out, indent=2, ensure_ascii=False)

        print(f"✅ Esquema guardado en: {schema_path.name}")

        # Inferir relaciones
        relaciones = infer_relationships(data)
        if relaciones:
            rel_path = output_dir / f"{json_file.stem}.relations.csv"
            with open(rel_path, "w", encoding="utf-8", newline='') as rel_file:
                writer = csv.writer(rel_file)
                writer.writerow(["parent_node", "child_node", "json_path"])
                for parent, child, path in relaciones:
                    writer.writerow([parent, child, path])
            print(f"🔗 Relaciones inferidas en: {rel_path.name}")
        else:
            print("ℹ️ No se detectaron relaciones padre-hijo en este archivo.")


if __name__ == "__main__":
    base_dir = Path(__file__).parent.parent.parent  # raíz de data_transform
    input_json_dir = base_dir / "data" / "limpios_json"
    output_schema_dir = base_dir / "data" / "json_schemas"

    generar_schemas(input_json_dir, output_schema_dir)
    print("✅ Proceso completado.")