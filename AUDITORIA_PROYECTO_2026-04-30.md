# Auditoria del proyecto - 2026-04-30

Proyecto auditado: `data_transform`  
Ruta local: `C:\Users\Alumno\Desktop\IA\githubb\data_transform`  
Fecha de revision: 2026-04-30  

Nota: este informe refleja el estado observado antes de la remediacion FASE 0.
Algunos hallazgos quedan conservados como evidencia historica aunque hayan sido
resueltos en commits posteriores.

## Resumen ejecutivo

El proyecto tiene una base funcional clara: scripts Python para limpieza de JSON OCR, conversiones a CSV/Markdown/PDF, generacion de nodos y relaciones para Neo4j, y modulos recientes para EusKorpus. La documentacion historica de Neo4j indica una importacion validada de 2.414.855 nodos y 2.414.850 relaciones con 0,00% de desviacion.

El estado actual, sin embargo, no es completamente reproducible desde un clon limpio. La suite de pruebas falla por dependencias no declaradas, hay scripts que ejecutan logica al importarse, falta configuracion moderna de proyecto/CI y algunas instrucciones del README no estan sincronizadas con el codigo actual.

Estado global recomendado: **usable como toolkit interno, no listo aun como release reproducible sin ajustes**.

## Snapshot tecnico

| Area | Estado observado |
| --- | --- |
| Rama Git | `main...origin/main` |
| Cambios versionados al inicio | Sin cambios pendientes |
| Python local usado | `Python 3.14.3` |
| Archivos detectados | 39 archivos relevantes antes del informe |
| Codigo Python | 18 archivos `.py` |
| Documentacion Markdown | 6 archivos `.md` |
| Configuracion de entorno | `.env.example` existe; `.env` esta ignorado |
| CI | No se detecto `.github/` |
| Configuracion pytest/ruff/pyproject | No se detecto `pytest.ini`, `pyproject.toml`, `ruff.toml` ni `.pre-commit-config.yaml` |
| Licencia | README muestra badge MIT, pero no existe archivo `LICENSE` |
| Directorio `data/` | No existe en el repositorio actual |

## Verificaciones ejecutadas

| Comando | Resultado |
| --- | --- |
| `git status --short --branch` | Rama `main...origin/main`; sin cambios versionados al inicio |
| `python --version` | `Python 3.14.3` |
| `python -m pytest -q` | Falla durante coleccion/importacion por `ModuleNotFoundError: No module named 'requests'` en `scripts/euskorpus/ehaa_scraper.py` |
| `python -B validate_csv.py` | Falla por CSV hardcodeado inexistente: `grafos\datos_grafos\AirTAC-Product-Catalogue-EU-ES_nodes.csv` |
| `pip check` | Sin conflictos entre paquetes instalados localmente |
| Busqueda de secretos | No se encontro `.env`; `.env.example` no contiene password real |

Nota: la ejecucion de pytest creo caches ignoradas (`__pycache__`) y un directorio temporal `pytest-cache-files-iyuqhp6a` con error de acceso al recorrerlo. Esos artefactos temporales se limpiaron tras la auditoria.

## Estado por componente

### Limpieza y normalizacion

Componente principal: `scripts/limpiezaD/clean_json_text.py`.

Puntos fuertes:

- Script autocontenido con libreria estandar.
- Soporta dry-run, overwrite, reporte CSV y limpieza Unicode.
- Hay reportes de limpieza en `info_doc/clean_report.csv` e `infodoc/clean_report.csv`.

Riesgos:

- Existen dos carpetas casi iguales, `info_doc` e `infodoc`, con el mismo `clean_report.csv`. Esto puede generar confusion de rutas.
- No hay pruebas automatizadas dedicadas a la limpieza Unicode.

### Conversiones de datos

Componentes:

- `scripts/tratamiento_datos/json_to_csv.py`
- `scripts/tratamiento_datos/csv_to_json.py`
- `scripts/tratamiento_datos/csv_to_md.py`
- `scripts/tratamiento_datos/csv_to_md_chunks.py`
- `scripts/tratamiento_datos/json_to_pdf.py`
- `scripts/tratamiento_datos/json_to_dual_pdf.py`

Puntos fuertes:

- Cubren formatos utiles para analisis, RAG y documentacion.
- `json_to_csv.py` tiene una funcion de extraccion razonablemente separada (`extract_rows`).

Riesgos:

- Varios scripts ejecutan `argparse` y logica en el nivel superior del modulo, por ejemplo `csv_to_md.py` y `csv_to_json.py`. Esto dificulta importar funciones en tests.
- No hay pruebas automatizadas para conversiones CSV/Markdown/PDF.
- Las dependencias PDF (`reportlab`, `PyMuPDF`) estan en `requirements.txt`, pero el entorno local auditado no las tiene instaladas.

### Grafo y Neo4j

Componentes:

- `grafos/scripts/json_to_graph.py`
- `grafos/scripts/run_pipeline_to_neo4j.py`
- `grafos/datos_grafos/*.metadata.json`
- `grafos/docs/validation.md`

Puntos fuertes:

- La documentacion historica muestra una importacion Neo4j validada al 100%.
- `json_to_graph.py` ya evita explosion innecesaria de nodos almacenando primitivos como propiedades.
- Hay metadatos versionados con conteos esperados por catalogo.
- La configuracion sensible de Neo4j se movio a variables de entorno y `.env.example`.

Riesgos:

- `run_pipeline_to_neo4j.py` valida variables de entorno al importarse (`NEO4J_PASSWORD`, `NEO4J_IMPORT_DIR`, `CYPHER_SHELL_PATH`). Esto complica los tests unitarios y cualquier importacion parcial.
- `copy_csv_to_import()` elimina todos los `*.csv` del directorio import de Neo4j antes de copiar los nuevos. Si ese directorio se comparte con otros procesos, puede borrar CSV ajenos.
- Las credenciales se pasan a `cypher-shell` con `-p`, lo que puede exponer el password en la lista de procesos del sistema.
- `CSV_OUTPUT_DIR` se resuelve relativo al directorio de ejecucion, no necesariamente relativo a la raiz del repo.

### EusKorpus

Componentes:

- `scripts/euskorpus/lang_detect.py`
- `scripts/euskorpus/domain_classifier.py`
- `scripts/euskorpus/ehaa_scraper.py`
- `tests/test_euskorpus.py`

Puntos fuertes:

- `lang_detect.py` y `domain_classifier.py` funcionan sin dependencias externas obligatorias.
- Durante pytest, las comprobaciones iniciales de idioma, dominio y almacenamiento de primitivos en `json_to_graph.py` pasaron antes del fallo del scraper.
- El scraper incluye rate limiting y reintentos.

Riesgos:

- `ehaa_scraper.py` necesita `requests`, `beautifulsoup4` y `lxml`, pero esas dependencias no estan en `requirements.txt`.
- Si faltan esas dependencias, `ehaa_scraper.py` llama a `sys.exit(1)` durante el import. Esto rompe pytest y cualquier codigo que quiera importar solo funciones puras como `parse_bopv_document`.
- `tests/test_euskorpus.py` es un script ejecutado al importarse, no una suite pytest idiomatica con funciones `test_*`.
- El test termina con `sys.exit(...)`, lo que causa errores internos en pytest cuando la coleccion falla a mitad.

### Dependencias y empaquetado

Estado observado:

- `requirements.txt` contiene muchas dependencias que parecen de una API web o backend (`fastapi`, `SQLAlchemy`, `redis`, `mysql-connector-python`, etc.) que no aparecen como usadas por el toolkit actual.
- Faltan dependencias realmente usadas: `requests`, `beautifulsoup4`, `lxml`, `genson`.
- No hay `pyproject.toml`, `setup.cfg` ni configuracion de extras por componente.

Impacto:

- La instalacion no queda minimizada ni reproducible por perfil de uso.
- Un usuario puede instalar `requirements.txt` y aun asi no poder ejecutar el scraper o el generador de schema.

### Documentacion

Puntos fuertes:

- README muy completo, bilingue y con arquitectura, quickstart y detalles operativos.
- Existen informes historicos de validacion Neo4j en `grafos/docs/`.

Desajustes:

- README todavia indica editar `grafos/scripts/run_pipeline_to_neo4j.py` para configurar credenciales, pero el codigo actual usa `.env`.
- README referencia una licencia MIT, pero falta `LICENSE`.
- README referencia estructura `data/` y artefactos de entrada/salida que no estan presentes en el repo actual.
- La configuracion de fin de linea esta duplicada: `.editorconfig` define `end_of_line = crlf` global, mientras `.gitattributes` fuerza LF para `.py`, `.md`, `.json`, etc.

## Hallazgos priorizados

### Alta prioridad

1. **La suite de pruebas no pasa desde el estado actual.**  
   Evidencia: `python -m pytest -q` falla por `ModuleNotFoundError: No module named 'requests'`.

2. **Dependencias declaradas incompletas.**  
   Faltan `requests`, `beautifulsoup4`, `lxml` y `genson`, todas importadas por scripts del repo.

3. **Imports con efectos laterales fuertes.**  
   `ehaa_scraper.py` hace `sys.exit(1)` si faltan dependencias; `tests/test_euskorpus.py` ejecuta todo el test al importarse.

4. **Riesgo de borrado amplio en importacion Neo4j.**  
   `run_pipeline_to_neo4j.py` elimina todos los CSV del directorio import de Neo4j. Debe limitarse a archivos generados por este proyecto o pedir confirmacion.

### Media prioridad

1. **README desactualizado respecto a configuracion `.env`.**
2. **`validate_csv.py` no es reutilizable y falla en el repo actual por ruta hardcodeada.**
3. **No hay CI, linting ni configuracion pytest.**
4. **No hay datos sample ni `data/.gitkeep`, aunque el flujo documentado depende de `data/`.**
5. **Duplicidad `info_doc` / `infodoc`.**
6. **Falta `LICENSE` pese al badge MIT.**

### Baja prioridad

1. **Dependencias sobredimensionadas en `requirements.txt`.**
2. **Inconsistencia potencial entre `.editorconfig` y `.gitattributes`.**
3. **Scripts antiguos con estilo compacto y menos testeable.**

## Recomendaciones

### Proxima iteracion recomendada

1. Arreglar dependencias:
   - Anadir `requests`, `beautifulsoup4`, `lxml`, `genson`.
   - Separar dependencias por perfil: `base`, `pdf`, `scraper`, `neo4j`, `dev`.
   - Eliminar o justificar dependencias backend no usadas.

2. Convertir tests a pytest real:
   - Crear funciones `test_*`.
   - Evitar `sys.exit` en tests.
   - Usar fixtures para HTML sample y JSON sample.

3. Hacer importables los scripts:
   - Mover `argparse` bajo `main()`.
   - Proteger ejecucion con `if __name__ == "__main__":`.
   - Cambiar `sys.exit` por excepciones controladas en codigo importable.

4. Hacer mas seguro `run_pipeline_to_neo4j.py`:
   - No validar `.env` al importarse; validarlo dentro de `main()`.
   - Anadir `--dry-run`.
   - Limitar borrado a prefijos conocidos o escribir en subdirectorio propio.
   - Evitar pasar password como argumento visible si `cypher-shell` permite alternativa mas segura.

5. Sincronizar documentacion:
   - Reemplazar instrucciones de "editar el script" por uso de `.env`.
   - Anadir `LICENSE`.
   - Documentar que los CSV grandes no estan versionados y que solo se versionan metadatos.
   - Aclarar `info_doc` vs `infodoc` y eliminar una carpeta si no hace falta.

6. Anadir estructura de proyecto:
   - `pyproject.toml` con pytest/ruff.
   - `.github/workflows/ci.yml`.
   - `data/.gitkeep` o `data/samples/` con ejemplo minimo.

## Conclusiones

El nucleo de transformacion y grafo parece valioso y ya tuvo validacion tecnica fuerte en Neo4j. La deuda principal no esta en la idea del pipeline, sino en reproducibilidad, automatizacion de pruebas y seguridad operativa alrededor de los scripts.

La mejora de mayor retorno seria convertir el proyecto en un toolkit instalable/testeable: dependencias correctas, scripts importables sin efectos laterales, pytest real y documentacion alineada con `.env`. Con eso, el proyecto pasaria de "funciona en el entorno del autor" a "cualquiera puede clonarlo, instalarlo y validar el estado en pocos minutos".
