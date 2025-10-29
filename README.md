# 📊 Data Transform Pipeline

**Industrial Catalog Processing & Knowledge Graph Construction**

_Part of the EcommJuice initiative for intelligent catalog digitization._

> Professional ETL pipeline for transforming OCR/AI-extracted documents into structured formats: CSV, JSON, Markdown, PDF, and Neo4j graph databases.

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.x-green.svg)](https://neo4j.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Last Commit](https://img.shields.io/github/last-commit/JuanHoob/data_transform)](https://github.com/JuanHoob/data_transform)

📧 **Contact**: delamorenajuan@gmail.com — for enterprise integration or dataset licensing.  
💼 **LinkedIn**: [linkedin.com/in/juandelamorenadev](https://www.linkedin.com/in/juandelamorenadev)

🧱 **Version**: 1.0.0 — Stable Release

---

## 📋 Table of Contents | Índice

- [English Documentation](#english-documentation)
  - [Overview](#overview)
  - [Features](#features)
  - [Architecture](#architecture)
  - [Installation](#installation)
  - [Quick Start](#quick-start)
  - [Pipeline Modules](#pipeline-modules)
- [Documentación en Español](#documentación-en-español)
  - [Descripción General](#descripción-general)
  - [Características](#características)
  - [Arquitectura](#arquitectura-1)
  - [Instalación](#instalación)
  - [Inicio Rápido](#inicio-rápido)
  - [Módulos del Pipeline](#módulos-del-pipeline)

---

# English Documentation

## Overview

**Data Transform** is an enterprise-grade ETL (Extract, Transform, Load) pipeline designed to process industrial technical catalogs extracted via OCR (Azure Document Intelligence) and transform them into multiple reusable formats optimized for:

- 📄 **Document Management**: Clean PDFs with enhanced traceability
- 📊 **Data Analysis**: Structured CSV/NDJSON for tabular operations
- 🤖 **RAG Pipelines**: Markdown chunks with metadata for AI retrieval
- 🕸️ **Knowledge Graphs**: Neo4j-ready nodes and relationships
- ✅ **Quality Assurance**: Automated validation and consistency checks

## Features

### Core Capabilities

✅ **Unicode Normalization**: Advanced text cleaning removing PUA characters, control codes, and malformed UTF-8  
✅ **Flexible Export**: Multi-format output (CSV, JSON, Markdown, PDF)  
✅ **Graph Generation**: Automatic structural analysis → Neo4j nodes & relationships  
✅ **Batch Processing**: Parallel processing of multiple documents  
✅ **Consistency Validation**: Post-import verification with configurable thresholds  
✅ **Metadata Tracking**: Complete audit trail for all transformations

### Technical Highlights

- 🚀 **Performance**: Handles 2M+ nodes with optimized batch commits (5000 rows/transaction)
- 🔍 **Validation**: Automated consistency checks (expected vs actual) with <2% deviation tolerance
- 📈 **Scalability**: Configurable recursion depth, memory-efficient processing
- 🛡️ **Reliability**: Error handling, rollback support, detailed logging

## Architecture

### Data Flow Diagram

```ASCII
┌──────────────────┐
│ Raw PDF + JSON   │  (Azure Document Intelligence)
│  (brutos_json)   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ clean_json_text  │  (Unicode normalization, PUA removal)
│      .py         │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   Clean JSON     │  (limpios_json)
│   + Metadata     │
└────┬─────────┬───┘
     │         │
     │         └──────────────────────┐
     │                                │
     ▼                                ▼
┌──────────────┐            ┌──────────────────┐
│  Converters  │            │  json_to_graph   │
│  (CSV, PDF,  │            │       .py        │
│   Markdown)  │            └────────┬─────────┘
└──────────────┘                     │
                                     ▼
                          ┌──────────────────────┐
                          │ nodes.csv + rels.csv │
                          │  + .metadata.json    │
                          └──────────┬───────────┘
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │ run_pipeline_to_neo4j│
                          │        .py           │
                          └──────────┬───────────┘
                                     │
                                     ▼
                          ┌──────────────────────────┐
                          │       Neo4j DB           │
                          │   (nodes + relations)    │
                          │   (CSV import path)      │
                          └──────────┬───────────────┘
                                     │
                                     ▼
                          ┌──────────────────────────┐
                          │   Consistency Check      │
                          │    (±2% tolerance)       │
                          │  (configurable threshold)│
                          └──────────┬───────────────┘
                                     │
                                     ▼
                          ┌──────────────────────────┐
                          │        Report            │
                          │  (validation summary)    │
                          └──────────────────────────┘
```

### Directory Structure

```
data_transform/
│
├── data/
│   ├── brutos_json/          # Raw OCR JSON files (Azure DI)
│   ├── limpios_json/         # Cleaned & normalized JSON
│   ├── brutos_pdf/           # Source PDF files
│   └── json_schemas/         # JSON Schema definitions
│
├── exports/
│   ├── pdf/                  # Generated clean PDFs
│   ├── csv/                  # Structured CSV/NDJSON exports
│   ├── docs_md/              # Monolithic Markdown docs
│   └── md_chunks/            # Chunked Markdown with traceability
│
├── grafos/
│   ├── scripts/
│   │   ├── json_to_graph.py          # JSON → CSV converter
│   │   └── run_pipeline_to_neo4j.py  # Orchestrated Neo4j import
│   ├── datos_grafos/         # Generated nodes & relationships CSV
│   └── exports/              # Neo4j export artifacts
│
├── info_doc/
│   └── clean_report.csv      # Automated cleaning metrics
│
└── scripts/
    ├── limpiezaD/            # Text cleaning & normalization
    │   └── clean_json_text.py
    ├── tratamiento_datos/    # Format conversion utilities
    │   ├── json_to_csv.py
    │   ├── json_to_pdf.py
    │   ├── json_to_dual_pdf.py
    │   ├── csv_to_md.py
    │   └── csv_to_md_chunks.py
    └── utils/                # Support tools
        ├── generar_schema_json.py
        ├── generar_csv_relaciones_neo4j.py
        └── consolidar_nodos.py
```

## Installation

### Prerequisites

- Python 3.11+
- Neo4j Desktop 5.x (for graph functionality)
- Git

### Setup

```bash
# Clone repository
git clone https://github.com/JuanHoob/data_transform.git
cd data_transform

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/Mac)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Neo4j Configuration

> **⚠️ Important**: Update Neo4j path and credentials before first run!

Edit `grafos/scripts/run_pipeline_to_neo4j.py`:

```python
# REQUIRED: Update these values for your environment
NEO4J_IMPORT_DIR = Path(r"C:\Users\<user>\.Neo4jDesktop2\Data\dbmss\<db-id>\import")
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "your_password"

# Optional customization
NODE_LABEL = "DataNode"
RELATIONSHIP_TYPE = "TIENE"
THRESHOLD = 0.02  # 2% tolerance for consistency validation
```

**How to find your Neo4j import directory:**

1. Open Neo4j Desktop
2. Select your database → Manage → Open Folder
3. Navigate to `import/` subdirectory
4. Copy the full path

## Quick Start

> 📖 **Note**: Scroll down for Spanish version / Desplázate hacia abajo para la versión en español

### 1. Clean Raw OCR JSON

```powershell
python scripts\limpiezaD\clean_json_text.py `
  --in data\brutos_json `
  --out data\limpios_json `
  --report info_doc\clean_report.csv `
  --overwrite
```

### 2. Convert to CSV

```powershell
python scripts\tratamiento_datos\json_to_csv.py `
  --in data\limpios_json `
  --out exports\csv
```

### 3. Generate Knowledge Graph (Full Pipeline)

> 💡 **Tip**: Run each step independently first to isolate performance issues.

```powershell
python grafos\scripts\run_pipeline_to_neo4j.py
```

**Output Example:**

```
============================================================
PIPELINE: JSON -> CSV -> Neo4j
============================================================

PASO 1: Generacion de CSVs
PASO 2: Copia a Neo4j import
  Eliminado CSV antiguo: old_file.csv
  Copiado: AirTAC-Booklet-EU-EN_nodes.csv

PASO 3: Creacion de indices
Indices creados

PASO 4: Importacion a Neo4j
Importando: AirTAC-Booklet-EU-EN
  Nodos cargados
  Relaciones cargadas

============================================================
PASO 5: Verificacion de consistencia
============================================================

Esperados (metadatos):
  Nodos: 2,414,855
  Relaciones: 2,414,850

Importados (Neo4j):
  Nodos: 2,414,855
  Relaciones: 2,414,850

✅ Nodos: Desviacion 0.00% (OK)
✅ Relaciones: Desviacion 0.00% (OK)

✅ Pipeline completed successfully
```

## Pipeline Modules

> 📖 **Note**: Scroll down for Spanish version / Desplázate hacia abajo para la versión en español

### 🧹 Text Cleaning (`clean_json_text.py`)

**Purpose**: Normalize Unicode, remove artifacts, map problematic glyphs

**Features**:

- NFC normalization
- PUA character removal
- Control code filtering (preserves `\n`, `\t`)
- Smart quote/dash mapping
- Detailed metrics reporting

**Usage**:

```bash
python scripts/limpiezaD/clean_json_text.py \
  --in data/brutos_json \
  --out data/limpios_json \
  --report info_doc/clean_report.csv \
  --overwrite
```

**Options**:

- `--dry-run`: Preview changes without writing
- `--keys-only`: Clean only specific JSON keys
- `--rules <yaml>`: Custom replacement rules

---

### 🔄 Format Converters (`tratamiento_datos/`)

#### JSON → CSV

```bash
python scripts/tratamiento_datos/json_to_csv.py \
  --in data/limpios_json \
  --out exports/csv
```

#### JSON → PDF (Clean Text)

```bash
python scripts/tratamiento_datos/json_to_pdf.py \
  --json data/limpios_json/catalog.json \
  --out exports/pdf/catalog_clean.pdf \
  --title "Catalog - Clean Text"
```

#### JSON → Dual PDF (Text + Original)

```bash
python scripts/tratamiento_datos/json_to_dual_pdf.py \
  --json data/limpios_json/catalog.json \
  --pdf data/brutos_pdf/catalog.pdf \
  --out exports/pdf/catalog_dual.pdf
```

#### CSV → Markdown Chunks

```bash
python scripts/tratamiento_datos/csv_to_md_chunks.py \
  --in exports/csv \
  --out exports/md_chunks
```

---

### 🕸️ Graph Generation (`grafos/scripts/`)

#### `json_to_graph.py`

**Purpose**: Transform JSON into Neo4j-compatible CSV files

**Key Features**:

- **Structural nodes only**: Creates nodes for `dict`/`list`, stores primitives as properties
- **ID sanitization**: Neo4j-safe IDs (`AirTAC_Booklet_pages_0_words`)
- **Depth control**: `--max-depth` prevents infinite recursion (default: 50)
- **Metadata generation**: Exports `.metadata.json` with totals, timestamps, schema

**Generated Files**:

- `*_nodes.csv`: Structural nodes with properties
- `*_relationships.csv`: Parent-child connections
- `*.metadata.json`: Import validation data

**Usage**:

```bash
python grafos/scripts/json_to_graph.py
python grafos/scripts/json_to_graph.py <input_dir> <output_dir> --max-depth 30
```

**CSV Structure**:

```csv
id,label,name,source,type,path,depth,length,properties
AirTAC_root,ObjectNode,root,AirTAC-Booklet,dict,root,0,,"{\"apiVersion\":\"2023-07-31\"}"
```

---

#### `run_pipeline_to_neo4j.py`

**Purpose**: Orchestrate end-to-end JSON → Neo4j import

**Pipeline Steps**:

1. **Generate CSVs**: Executes `json_to_graph.py`
2. **Discover Pairs**: Auto-detects CSV + metadata files
3. **Clean Import Dir**: Removes old CSVs from Neo4j import folder
4. **Copy Files**: Transfers new CSVs to Neo4j import directory
5. **Create Indexes**: Sets up constraints (unique ID) and indexes (source, type)
6. **Load Data**: Batch import with `USING PERIODIC COMMIT 5000`
7. **Verify Consistency**: Compares expected (metadata) vs actual (Neo4j) counts

**Key Functions**:

```python
discover_csv_files()        # Auto-detect CSV pairs + metadata
copy_csv_to_import()        # Stage files for Neo4j
create_indexes()            # CREATE CONSTRAINT + INDEX
load_csv_pair()             # MERGE nodes & relationships
verify_import_consistency() # Validation with % thresholds
```

**Configuration**:

```python
# Edit these in run_pipeline_to_neo4j.py
NEO4J_IMPORT_DIR = Path(r"C:\...\Neo4jDesktop2\...\import")
NODE_LABEL = "DataNode"
RELATIONSHIP_TYPE = "TIENE"
THRESHOLD = 0.02  # 2% tolerance
```

**Cypher Optimization**:

```cypher
USING PERIODIC COMMIT 5000
LOAD CSV WITH HEADERS FROM 'file:///nodes.csv' AS row
MERGE (n:DataNode {id: row.id})
SET n.name = row.name,
    n.depth = toInteger(row.depth),
    n.source = row.source,
    n.type = row.type
RETURN count(n);  -- Quick validation
```

---

## Best Practices

### Performance

- Use `--max-depth` to limit recursion in large JSONs
- Increase `PERIODIC COMMIT` size for large datasets (test 10000)
- Run during off-peak hours for Neo4j imports

### Data Quality

- Always run `clean_json_text.py` before conversions
- Review `clean_report.csv` for anomalies
- Set consistency threshold <2% for production imports

### Maintenance

- Clear Neo4j import directory before each run (handled automatically)
- Backup databases before large imports
- Monitor `verify_import_consistency()` output

---

## Metrics & Performance

### Typical Processing Times

<div align="center">

| Operation         | Dataset Size           | Time     | Nodes/Relations |
| ----------------- | ---------------------- | -------- | --------------- |
| JSON Cleaning     | 5 files (~20MB each)   | ~45s     | N/A             |
| CSV Generation    | 5 files                | ~2min    | 2.4M nodes      |
| Neo4j Import      | 2.4M nodes + 2.4M rels | ~8-12min | 4.8M total      |
| Consistency Check | 4.8M entities          | ~15s     | <0.1% deviation |

</div>

### Average Metrics per Catalog

- **Nodes**: 400k-500k structural elements
- **Relationships**: ~1:1 ratio with nodes
- **Depth**: Average 4-6 levels (max configurable: 50)
- **CSV Size**: 50-80MB per pair (nodes + relationships)

### Quality Metrics (clean_json_text.py)

- **Strings processed**: 100k-150k per catalog
- **Characters removed**: 0.5-2% (control codes, PUA)
- **Characters mapped**: 1-3% (smart quotes, dashes, NBSP)
- **Strings changed**: 15-25% (typically whitespace normalization)

> For detailed historical metrics, see `grafos/docs/validation.md`

---

## Troubleshooting

### Common Issues

**"No se encontraron pares CSV"**
→ Run `json_to_graph.py` first to generate CSVs

**"Error al cargar nodos"**
→ Check Neo4j import directory permissions  
→ Verify `cypher-shell` is in PATH

**High consistency deviation (>2%)**
→ Check for duplicate IDs in source JSON  
→ Verify CSV encoding (must be UTF-8)  
→ Review `clean_report.csv` for excessive character removal

---

## License

MIT License - See [LICENSE](LICENSE) for details

## Author

**Juan de la Morena** ([@JuanHoob](https://github.com/JuanHoob))  
💼 LinkedIn: [linkedin.com/in/juandelamorenadev](https://www.linkedin.com/in/juandelamorenadev)  
EcommJuice Project · 2025

---

# Documentación en Español

## Descripción General

**Data Transform** es un pipeline ETL (Extracción, Transformación, Carga) de nivel empresarial diseñado para procesar catálogos técnicos industriales extraídos mediante OCR (Azure Document Intelligence) y transformarlos en múltiples formatos reutilizables optimizados para:

- 📄 **Gestión Documental**: PDFs limpios con trazabilidad mejorada
- 📊 **Análisis de Datos**: CSV/NDJSON estructurados para operaciones tabulares
- 🤖 **Pipelines RAG**: Fragmentos Markdown con metadatos para recuperación IA
- 🕸️ **Grafos de Conocimiento**: Nodos y relaciones listos para Neo4j
- ✅ **Garantía de Calidad**: Validación y verificaciones de consistencia automatizadas

## Características

### Capacidades Principales

✅ **Normalización Unicode**: Limpieza avanzada eliminando caracteres PUA, códigos de control y UTF-8 malformado  
✅ **Exportación Flexible**: Salida multi-formato (CSV, JSON, Markdown, PDF)  
✅ **Generación de Grafos**: Análisis estructural automático → nodos y relaciones Neo4j  
✅ **Procesamiento por Lotes**: Procesamiento paralelo de múltiples documentos  
✅ **Validación de Consistencia**: Verificación post-importación con umbrales configurables  
✅ **Seguimiento de Metadatos**: Trazabilidad completa de todas las transformaciones

### Aspectos Técnicos Destacados

- 🚀 **Rendimiento**: Maneja 2M+ nodos con commits optimizados en lotes (5000 filas/transacción)
- 🔍 **Validación**: Verificaciones de consistencia automatizadas (esperado vs real) con tolerancia <2%
- 📈 **Escalabilidad**: Profundidad de recursión configurable, procesamiento eficiente en memoria
- 🛡️ **Fiabilidad**: Manejo de errores, soporte de rollback, registro detallado

## Arquitectura

Ver estructura en [sección inglesa](#architecture)

## Instalación

### Requisitos Previos

- Python 3.11+
- Neo4j Desktop 5.x (para funcionalidad de grafos)
- Git

### Configuración

```bash
# Clonar repositorio
git clone https://github.com/JuanHoob/data_transform.git
cd data_transform

# Crear entorno virtual
python -m venv .venv

# Activar (Windows)
.venv\Scripts\activate

# Activar (Linux/Mac)
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### Configuración Neo4j

Editar `grafos/scripts/run_pipeline_to_neo4j.py`:

```python
NEO4J_IMPORT_DIR = Path(r"C:\Users\<usuario>\.Neo4jDesktop2\Data\dbmss\<db-id>\import")
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "tu_contraseña"
```

## Inicio Rápido

> 📖 **Nota**: Scroll down for Spanish version / Desplázate hacia abajo para la versión en español

### 1. Limpiar JSON OCR Brutos

```powershell
python scripts\limpiezaD\clean_json_text.py `
  --in data\brutos_json `
  --out data\limpios_json `
  --report info_doc\clean_report.csv `
  --overwrite
```

### 2. Convertir a CSV

```powershell
python scripts\tratamiento_datos\json_to_csv.py `
  --in data\limpios_json `
  --out exports\csv
```

### 3. Generar Grafo de Conocimiento (Pipeline Completo)

> 💡 **Consejo**: Ejecuta cada paso independientemente primero para aislar problemas de rendimiento.

```powershell
python grafos\scripts\run_pipeline_to_neo4j.py
```

**Ejemplo de Salida:**

```
============================================================
PIPELINE: JSON -> CSV -> Neo4j
============================================================

PASO 1: Generacion de CSVs
PASO 2: Copia a Neo4j import
  Eliminado CSV antiguo: archivo_viejo.csv
  Copiado: AirTAC-Booklet-EU-EN_nodes.csv

PASO 3: Creacion de indices
Indices creados

PASO 4: Importacion a Neo4j
Importando: AirTAC-Booklet-EU-EN
  Nodos cargados
  Relaciones cargadas

============================================================
PASO 5: Verificacion de consistencia
============================================================

Esperados (metadatos):
  Nodos: 2,414,855
  Relaciones: 2,414,850

Importados (Neo4j):
  Nodos: 2,414,855
  Relaciones: 2,414,850

✅ Nodos: Desviacion 0.00% (OK)
✅ Relaciones: Desviacion 0.00% (OK)

✅ Pipeline finalizado correctamente
```

## Módulos del Pipeline

> 📖 **Nota**: Scroll down for Spanish version / Desplázate hacia abajo para la versión en español

### 🧹 Limpieza de Texto (`clean_json_text.py`)

**Propósito**: Normalizar Unicode, eliminar artefactos, mapear glifos problemáticos

**Características**:

- Normalización NFC
- Eliminación de caracteres PUA
- Filtrado de códigos de control (preserva `\n`, `\t`)
- Mapeo inteligente de comillas/guiones
- Reporte detallado de métricas

**Uso**:

```bash
python scripts/limpiezaD/clean_json_text.py \
  --in data/brutos_json \
  --out data/limpios_json \
  --report info_doc/clean_report.csv \
  --overwrite
```

**Opciones**:

- `--dry-run`: Vista previa sin escribir cambios
- `--keys-only`: Limpiar solo claves JSON específicas
- `--rules <yaml>`: Reglas de reemplazo personalizadas

---

### 🔄 Conversores de Formato (`tratamiento_datos/`)

#### JSON → CSV

```bash
python scripts/tratamiento_datos/json_to_csv.py \
  --in data/limpios_json \
  --out exports/csv
```

#### JSON → PDF (Texto Limpio)

```bash
python scripts/tratamiento_datos/json_to_pdf.py \
  --json data/limpios_json/catalogo.json \
  --out exports/pdf/catalogo_limpio.pdf \
  --title "Catálogo - Texto Limpio"
```

#### JSON → PDF Dual (Texto + Original)

```bash
python scripts/tratamiento_datos/json_to_dual_pdf.py \
  --json data/limpios_json/catalogo.json \
  --pdf data/brutos_pdf/catalogo.pdf \
  --out exports/pdf/catalogo_dual.pdf
```

#### CSV → Fragmentos Markdown

```bash
python scripts/tratamiento_datos/csv_to_md_chunks.py \
  --in exports/csv \
  --out exports/md_chunks
```

---

### 🕸️ Generación de Grafos (`grafos/scripts/`)

#### `json_to_graph.py`

**Propósito**: Transformar JSON en archivos CSV compatibles con Neo4j

**Características Clave**:

- **Solo nodos estructurales**: Crea nodos para `dict`/`list`, almacena primitivos como propiedades
- **Sanitización de IDs**: IDs seguros para Neo4j (`AirTAC_Booklet_pages_0_words`)
- **Control de profundidad**: `--max-depth` previene recursión infinita (predeterminado: 50)
- **Generación de metadatos**: Exporta `.metadata.json` con totales, timestamps, esquema

**Archivos Generados**:

- `*_nodes.csv`: Nodos estructurales con propiedades
- `*_relationships.csv`: Conexiones padre-hijo
- `*.metadata.json`: Datos de validación de importación

**Uso**:

```bash
python grafos/scripts/json_to_graph.py
python grafos/scripts/json_to_graph.py <dir_entrada> <dir_salida> --max-depth 30
```

---

#### `run_pipeline_to_neo4j.py`

**Propósito**: Orquestar importación completa JSON → Neo4j

**Pasos del Pipeline**:

1. **Generar CSVs**: Ejecuta `json_to_graph.py`
2. **Descubrir Pares**: Auto-detecta archivos CSV + metadatos
3. **Limpiar Directorio Import**: Elimina CSVs antiguos de la carpeta import de Neo4j
4. **Copiar Archivos**: Transfiere nuevos CSVs al directorio import de Neo4j
5. **Crear Índices**: Configura constraints (ID único) e índices (source, type)
6. **Cargar Datos**: Importación por lotes con `USING PERIODIC COMMIT 5000`
7. **Verificar Consistencia**: Compara conteos esperados (metadatos) vs reales (Neo4j)

**Funciones Clave**:

```python
discover_csv_files()        # Auto-detectar pares CSV + metadatos
copy_csv_to_import()        # Preparar archivos para Neo4j
create_indexes()            # CREATE CONSTRAINT + INDEX
load_csv_pair()             # MERGE nodos y relaciones
verify_import_consistency() # Validación con umbrales %
```

**Configuración**:

```python
# Editar estos valores en run_pipeline_to_neo4j.py
NEO4J_IMPORT_DIR = Path(r"C:\...\Neo4jDesktop2\...\import")
NODE_LABEL = "DataNode"
RELATIONSHIP_TYPE = "TIENE"
THRESHOLD = 0.02  # 2% tolerancia
```

**Optimización Cypher**:

```cypher
USING PERIODIC COMMIT 5000
LOAD CSV WITH HEADERS FROM 'file:///nodes.csv' AS row
MERGE (n:DataNode {id: row.id})
SET n.name = row.name,
    n.depth = toInteger(row.depth),
    n.source = row.source,
    n.type = row.type
RETURN count(n);  -- Validación rápida
```

---

## Buenas Prácticas

### Rendimiento

- Usar `--max-depth` para limitar recursión en JSONs grandes
- Aumentar tamaño de `PERIODIC COMMIT` para conjuntos de datos grandes (probar 10000)
- Ejecutar durante horas no pico para importaciones Neo4j

### Calidad de Datos

- Siempre ejecutar `clean_json_text.py` antes de conversiones
- Revisar `clean_report.csv` para detectar anomalías
- Establecer umbral de consistencia <2% para importaciones de producción

### Mantenimiento

- Limpiar directorio import de Neo4j antes de cada ejecución (se maneja automáticamente)
- Hacer backup de bases de datos antes de importaciones grandes
- Monitorear salida de `verify_import_consistency()`

---

## Solución de Problemas

### Problemas Comunes

**"No se encontraron pares CSV"**
→ Ejecutar primero `json_to_graph.py` para generar CSVs

**"Error al cargar nodos"**
→ Verificar permisos del directorio import de Neo4j  
→ Verificar que `cypher-shell` esté en PATH

**Alta desviación de consistencia (>2%)**
→ Verificar IDs duplicados en JSON fuente  
→ Verificar codificación CSV (debe ser UTF-8)  
→ Revisar `clean_report.csv` para eliminación excesiva de caracteres

---

## Licencia

Licencia MIT - Ver [LICENSE](LICENSE) para detalles

## Autor

**Juan de la Morena** ([@JuanHoob](https://github.com/JuanHoob))  
💼 LinkedIn: [linkedin.com/in/juandelamorenadev](https://www.linkedin.com/in/juandelamorenadev)  
Proyecto EcommJuice · 2025

---

## 🔗 Enlaces Útiles | Useful Links

- [Neo4j Documentation](https://neo4j.com/docs/)
- [Azure Document Intelligence](https://azure.microsoft.com/en-us/services/cognitive-services/form-recognizer/)
- [ReportLab PDF Library](https://www.reportlab.com/opensource/)
- [PyMuPDF (fitz)](https://pymupdf.readthedocs.io/)

---

## 🧾 Validation & Audit Reports

After each import, the pipeline generates a consistency summary comparing expected vs imported entities.

These reports can be exported automatically to:

- **`grafos/docs/validation.md`** — Historical log of import accuracy
- **`grafos/exports/consistency_report.json`** — Machine-readable JSON for CI/CD integration

**Example Output:**

```
✅ Nodes: 2,414,855 (0.00% deviation)
✅ Relationships: 2,414,850 (0.00% deviation)
```

For troubleshooting patterns and historical benchmarks, see the [Validation Documentation](grafos/docs/validation.md).

---

## 📝 Changelog

### v1.0.0 (2025-01-28)

- ✨ Initial release
- ✅ Complete ETL pipeline: JSON → CSV → Neo4j
- ✅ Unicode normalization with detailed metrics
- ✅ Automated consistency validation
- ✅ Multi-format export (CSV, JSON, MD, PDF)
- ✅ Graph generation with depth control
- ✅ Bilingual documentation (EN/ES)

### 🚀 v1.1.0 (Planned)

- 🔄 AuraDB remote import support
- 📊 JSON incremental diff loader (only new/changed documents)
- 🎯 Advanced query templates for common graph patterns
- 📈 Performance profiler and optimization recommendations
- 🌐 REST API for pipeline orchestration

---

## 🤝 Contributing | Contribuciones

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Las contribuciones son bienvenidas! Por favor:

1. Hacer fork del repositorio
2. Crear una rama de funcionalidad (`git checkout -b feature/funcionalidad-increible`)
3. Hacer commit de los cambios (`git commit -m 'Añadir funcionalidad increíble'`)
4. Hacer push a la rama (`git push origin feature/funcionalidad-increible`)
5. Abrir un Pull Request

---

## 🔗 Related Tools & Integrations

This pipeline is part of the **EcommJuice Data Engineering Stack**:

- **NextPC**: Next-generation product catalog system (coming soon)
- **Invikta Automation**: Industrial inventory management integration
- **GraphRAG**: Knowledge graph-powered retrieval for AI applications
- **Azure DI Connector**: Automated OCR pipeline orchestration

> 💡 Interested in enterprise integration? Contact us at delamorenajuan@gmail.com

---

**⚡ Built with Python | Construido con Python**

_Designed and engineered with focus on reproducibility, transparency, and scale._

_Maintained by EcommJuice Data Engineering · 2025_
