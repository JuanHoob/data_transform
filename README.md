# PDF.JSON — Flujo

## Estructura
- `data/brutos_json/` → JSON DI originales (para dual y como master).
- `data/limpios_json/` → JSON normalizados (entrada a indexar/convertir).
- `data/brutos_pdf/` → PDFs fuente (para dual).
- `exports/pdf/` → PDFs generados desde JSON limpio.
- `exports/csv/` → tabulados/ndjson/csv tras tratamiento.
- `exports/docs_md/` → (si generas doc MD monolítico).
- `exports/md_chunks/` → Markdown **por fragmento** (chunks trazables).
- `scripts/limpiezaD/` → filtros de limpieza/corrección.
- `scripts/tratamiento_de_datos/` → CSV→NDJSON/MD, etc.

## Comandos típicos

### 1) Normalizar JSON (símbolos y espacios)
```powershell
python .\scripts\limpiezaD\filter_normaliza.py `
  --in ".\data\brutos_json" `
  --out ".\data\limpios_json" `
  --mode correccion
