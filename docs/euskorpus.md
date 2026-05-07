# EusKorpus

EusKorpus es el modulo experimental para crear corpus EHAA/BOPV a partir del
HTML publico de euskadi.eus.

## Instalacion

```powershell
pip install -e ".[scraper,dev]"
```

## Uso basico

Scraping de una URL directa de documento:

```powershell
python -m scripts.euskorpus.ehaa_scraper `
  --url "https://www.euskadi.eus/bopv2/datos/2024/10/2404929a.shtml" `
  --output data/limpios_json/ehaa
```

Vista previa sin escribir archivos:

```powershell
python -m scripts.euskorpus.ehaa_scraper `
  --url "https://www.euskadi.eus/bopv2/datos/2024/10/2404929a.shtml" `
  --dry-run
```

Procesar tambien la version paralela ES/EU cuando el patron lo permite:

```powershell
python -m scripts.euskorpus.ehaa_scraper `
  --url "https://www.euskadi.eus/bopv2/datos/2024/10/2404929a.shtml" `
  --with-parallel `
  --output data/limpios_json/ehaa
```

Procesar documentos enlazados desde un sumario:

```powershell
python -m scripts.euskorpus.ehaa_scraper `
  --summary-url "https://www.euskadi.eus/bopv2/datos/2024/10/s24_0210.shtml" `
  --output data/limpios_json/ehaa
```

## Flujo recomendado

El flujo actual recomendado es:

```powershell
python -m scripts.euskorpus.ehaa_scraper `
  --url "https://www.euskadi.eus/bopv2/datos/2024/10/2404929a.shtml" `
  --output data/limpios_json/ehaa

python -m scripts.euskorpus.lang_detect `
  --file data/limpios_json/ehaa/NOMBRE_ARCHIVO.json

python -m scripts.euskorpus.domain_classifier `
  --file data/limpios_json/ehaa/NOMBRE_ARCHIVO.json
```

## Esquema JSON de salida

Ejemplo reducido:

```json
{
  "source": "EHAA/BOPV",
  "source_url": "https://www.euskadi.eus/bopv2/datos/2024/10/2404929a.shtml",
  "document_id": "2404929",
  "language": "es",
  "parallel_url": "https://www.euskadi.eus/bopv2/datos/2024/10/2404929e.shtml",
  "title": "RESOLUCION de 17 de octubre de 2024...",
  "date_published": "2024-10-28",
  "section": "OTRAS DISPOSICIONES",
  "bopv_number": "210",
  "order": "4929",
  "paragraphs": [
    {
      "index": 0,
      "text": "RESOLUCION de 17 de octubre de 2024...",
      "language": "es"
    }
  ],
  "metadata": {
    "parser_version": "bopv-html-v1",
    "scraped_at": "2026-05-07T00:00:00Z",
    "raw_classes_detected": ["BOPVDetalle", "BOPVTitulo"],
    "paragraph_count": 98
  }
}
```

Los nombres de salida siguen este patron:

```text
ehaa_bopv_{date}_{document_id}_{language}.json
```

Ejemplo:

```text
ehaa_bopv_2024-10-28_2404929_es.json
```

## Estado y limitaciones

- Scraping por URL directa: soportado.
- Scraping por sumario: soportado.
- Scraping por anno: no soportado todavia. La opcion `--year` devuelve un error claro.
- Los tests normales no usan red. El test live esta saltado salvo que se defina
  `EUSKORPUS_RUN_LIVE_TESTS=1`.
- Los datos grandes no se versionan. Solo hay HTML real pequeno en `tests/data/`.
- Los pares ES/EU se construyen con una heuristica documentada del BOPV actual:
  `2404929a.shtml` para castellano y `2404929e.shtml` para euskera.
- La heuristica de idioma devuelve `None` si el patron no permite inferencia.
