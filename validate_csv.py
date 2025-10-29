import csv
import sys

csv.field_size_limit(131072 * 10)  # Limit razonable

csv_file = r'grafos\datos_grafos\AirTAC-Product-Catalogue-EU-ES_nodes.csv'

with open(csv_file, encoding='utf-8') as f:
    reader = csv.reader(f)
    count = sum(1 for _ in reader)
    print(f'✅ CSV valido - {count} filas leidas correctamente')
