#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Consolida todos los archivos *_nodes.csv en un único archivo invikta_bbdd_nodes.csv
"""

import pandas as pd
import glob
import os

# Rutas
NODES_DIR = os.path.join("grafos", "datos_grafos")
OUTPUT_FILE = os.path.join(NODES_DIR, "invikta_bbdd_nodes.csv")

def main():
    # Buscar todos los archivos de nodos
    pattern = os.path.join(NODES_DIR, "*_nodes.csv")
    files = [f for f in glob.glob(pattern) if not f.endswith("invikta_bbdd_nodes.csv")]
    
    if not files:
        print(f"No se encontraron archivos de nodos en {NODES_DIR}")
        return
    
    print(f"Encontrados {len(files)} archivos de nodos:")
    for f in files:
        print(f"  - {os.path.basename(f)}")
    
    # Leer y consolidar
    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f, dtype=str).fillna("")
            dfs.append(df)
            print(f"  ✓ Leído: {os.path.basename(f)} ({len(df)} nodos)")
        except Exception as e:
            print(f"  ✗ Error leyendo {os.path.basename(f)}: {e}")
    
    if not dfs:
        print("No se pudieron leer archivos de nodos")
        return
    
    # Concatenar y eliminar duplicados
    df_all = pd.concat(dfs, ignore_index=True)
    print(f"\nTotal de nodos antes de deduplicar: {len(df_all)}")
    
    # Deduplicar por 'id' si existe la columna
    if 'id' in df_all.columns:
        df_all = df_all.drop_duplicates(subset=['id'], keep='first')
        print(f"Total de nodos después de deduplicar: {len(df_all)}")
    
    # Guardar
    df_all.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ Archivo consolidado guardado: {OUTPUT_FILE}")
    print(f"   Columnas: {', '.join(df_all.columns)}")
    print(f"   Total nodos: {len(df_all)}")

if __name__ == "__main__":
    main()
