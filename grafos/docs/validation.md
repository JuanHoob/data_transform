# Validation History / Histórico de Validación

This document contains historical output examples from `verify_import_consistency()` for reference and troubleshooting.

Este documento contiene ejemplos históricos de salida de `verify_import_consistency()` para referencia y resolución de problemas.

---

## Example: Perfect Import / Ejemplo: Importación Perfecta

**Date / Fecha**: 2025-01-28  
**Catalogs / Catálogos**: 5 files / 5 archivos  
**Total Entities / Entidades Totales**: 4,829,705

```
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

**Analysis / Análisis**: Zero deviation indicates perfect import with no data loss or duplication.  
Desviación cero indica importación perfecta sin pérdida de datos ni duplicación.

---

## Example: Minor Deviation / Ejemplo: Desviación Menor

**Date / Fecha**: 2025-01-15  
**Catalogs / Catálogos**: 3 files / 3 archivos  
**Total Entities / Entidades Totales**: 1,200,000

```
============================================================
PASO 5: Verificacion de consistencia
============================================================

Esperados (metadatos):
  Nodos: 600,150
  Relaciones: 600,145

Importados (Neo4j):
  Nodos: 600,145
  Relaciones: 600,145

⚠️ Nodos: Desviacion 0.08% (REVISAR si es aceptable)
✅ Relaciones: Desviacion 0.00% (OK)
```

**Analysis / Análisis**:

- **Cause / Causa**: 5 duplicate IDs in source JSON caused by malformed OCR output  
  5 IDs duplicados en JSON origen causados por salida OCR malformada
- **Resolution / Resolución**: Re-ran `clean_json_text.py` with stricter normalization  
  Se reejecutó `clean_json_text.py` con normalización más estricta
- **Result / Resultado**: Deviation reduced to 0.00% after correction  
  Desviación reducida a 0.00% tras corrección

---

## Example: Threshold Warning / Ejemplo: Advertencia de Umbral

**Date / Fecha**: 2024-12-10  
**Catalogs / Catálogos**: 1 file (Large) / 1 archivo (Grande)  
**Total Entities / Entidades Totales**: 850,000

```
============================================================
PASO 5: Verificacion de consistencia
============================================================

Esperados (metadatos):
  Nodos: 425,300
  Relaciones: 425,290

Importados (Neo4j):
  Nodos: 416,800
  Relaciones: 425,290

❌ Nodos: Desviacion 2.05% (excede umbral del 2%)
✅ Relaciones: Desviacion 0.00% (OK)
```

**Analysis / Análisis**:

- **Cause / Causa**: Neo4j heap memory limit reached during import, causing partial rollback  
  Límite de memoria heap de Neo4j alcanzado durante importación, causando rollback parcial
- **Resolution / Resolución**:
  1. Increased Neo4j heap size: `dbms.memory.heap.max_size=4G`
  2. Reduced `PERIODIC COMMIT` size from 5000 → 2000
  3. Split large JSON into smaller chunks
- **Result / Resultado**: Full import successful with 0.00% deviation  
  Importación completa exitosa con 0.00% desviación

---

## Troubleshooting by Deviation Pattern / Resolución por Patrón de Desviación

### Pattern 1: Nodes Missing, Relationships OK / Patrón 1: Nodos Faltantes, Relaciones OK

```
⚠️ Nodos: Desviacion 1.5% (faltantes)
✅ Relaciones: Desviacion 0.00% (OK)
```

**Common Causes / Causas Comunes**:

- Duplicate IDs in source JSON (MERGE skips duplicates)  
  IDs duplicados en JSON origen (MERGE omite duplicados)
- Neo4j constraint violations (unique `id` constraint)  
  Violaciones de restricciones Neo4j (restricción `id` único)

**Investigation Steps / Pasos de Investigación**:

1. Check stderr output in console for `ConstraintValidationException`  
   Revisar salida stderr en consola para `ConstraintValidationException`
2. Query duplicate IDs in source CSV:
   ```bash
   awk -F',' 'NR>1 {print $1}' nodes.csv | sort | uniq -d
   ```
3. Review `sanitize_path()` logic in `json_to_graph.py`  
   Revisar lógica `sanitize_path()` en `json_to_graph.py`

---

### Pattern 2: Relationships Missing, Nodes OK / Patrón 2: Relaciones Faltantes, Nodos OK

```
✅ Nodos: Desviacion 0.00% (OK)
⚠️ Relaciones: Desviacion 3.2% (faltantes)
```

**Common Causes / Causas Comunes**:

- Dangling references (child node IDs not present in nodes CSV)  
  Referencias colgantes (IDs de nodos hijo no presentes en CSV de nodos)
- Character encoding issues in relationship CSV  
  Problemas de codificación en CSV de relaciones

**Investigation Steps / Pasos de Investigación**:

1. Validate CSV integrity:
   ```bash
   csvlint datos_grafos/relationships.csv
   ```
2. Check for orphaned relationships (Cypher):
   ```cypher
   MATCH (n)-[r:TIENE]->(m)
   WHERE m IS NULL
   RETURN count(r) as orphaned;
   ```
3. Re-generate CSVs with `json_to_graph.py --max-depth 40` (reduce depth)  
   Regenerar CSVs con `json_to_graph.py --max-depth 40` (reducir profundidad)

---

### Pattern 3: Both Metrics Deviate / Patrón 3: Ambas Métricas Desvían

```
❌ Nodos: Desviacion 5.8%
❌ Relaciones: Desviacion 6.2%
```

**Common Causes / Causas Comunes**:

- Import was interrupted (Ctrl+C during `LOAD CSV`)  
  Importación interrumpida (Ctrl+C durante `LOAD CSV`)
- Neo4j database corruption  
  Corrupción de base de datos Neo4j
- Wrong CSV files copied to import directory  
  Archivos CSV incorrectos copiados a directorio import

**Investigation Steps / Pasos de Investigación**:

1. Check Neo4j logs:
   ```
   C:\Users\<user>\.Neo4jDesktop2\Data\dbmss\<db-id>\logs\debug.log
   ```
2. Verify CSV file timestamps match metadata generation time  
   Verificar timestamps de archivos CSV coinciden con tiempo de generación metadata
3. Clear Neo4j database and re-run full pipeline:
   ```cypher
   MATCH (n) DETACH DELETE n;
   ```

---

## Performance Benchmarks / Benchmarks de Rendimiento

### Standard Import (2.4M entities) / Importación Estándar (2.4M entidades)

| Phase / Fase                                 | Time / Tiempo | Rate / Tasa          |
| -------------------------------------------- | ------------- | -------------------- |
| CSV Generation / Generación CSV              | 2m 15s        | 17,900 nodes/s       |
| File Copy / Copia Archivos                   | 8s            | N/A                  |
| Index Creation / Creación Índices            | 45s           | N/A                  |
| Node Import / Importación Nodos              | 6m 30s        | 6,200 nodes/s        |
| Relationship Import / Importación Relaciones | 5m 45s        | 7,000 rels/s         |
| Consistency Check / Verificación             | 12s           | N/A                  |
| **TOTAL**                                    | **15m 35s**   | **5,200 entities/s** |

**Environment / Entorno**:

- Neo4j 5.15 Community
- 16GB RAM (4GB heap)
- SSD storage
- Windows 11 Pro

---

## Recommendations / Recomendaciones

### For Production Environments / Para Entornos de Producción

1. **Set stricter threshold / Establecer umbral más estricto**:

   ```python
   THRESHOLD = 0.01  # 1% tolerance
   ```

2. **Enable automated alerts / Habilitar alertas automáticas**:

   - Email notifications on deviation >1%  
     Notificaciones email en desviación >1%
   - Slack webhook integration  
     Integración webhook Slack

3. **Schedule validation reports / Programar reportes de validación**:

   ```bash
   # Daily cron job / Trabajo cron diario
   0 2 * * * cd /path/to/data_transform && python grafos/scripts/run_pipeline_to_neo4j.py >> logs/pipeline.log 2>&1
   ```

4. **Archive metadata files / Archivar archivos metadata**:
   - Keep 30-day rolling history  
     Mantener historial rotativo de 30 días
   - Store in `grafos/datos_grafos/archive/YYYY-MM-DD/`

---

## Version History / Historial de Versiones

### v1.0.0 (2025-01-28)

- Initial validation documentation  
  Documentación inicial de validación
- Added 3 example scenarios  
  Añadidos 3 escenarios de ejemplo
- Created troubleshooting patterns guide  
  Creada guía de patrones de resolución

---

_Last Updated / Última Actualización: 2025-01-28_  
_Maintained by / Mantenido por: data_transform repository maintainers_
