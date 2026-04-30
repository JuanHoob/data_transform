# Datos de ejemplo

El directorio `data/` esta reservado para entradas y salidas locales del pipeline:
JSON OCR bruto, JSON limpio, PDFs de origen, CSV generados, Markdown y otros
artefactos derivados.

Los datos grandes y reales no se versionan en este repositorio. Las reglas de
`.gitignore` mantienen fuera los artefactos pesados para evitar subir corpus,
PDFs o CSV de produccion.

Los samples pequenos usados por la suite de tests viven en `tests/data/`.
