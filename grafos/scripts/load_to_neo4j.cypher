// Script para cargar los CSVs en Neo4j Browser
// Ejecuta estos comandos uno por uno en Neo4j Browser

// 1. Crear índices
CREATE INDEX DataNode_id IF NOT EXISTS FOR (n:DataNode) ON (n.id);
CREATE INDEX DataNode_source IF NOT EXISTS FOR (n:DataNode) ON (n.source);

// 2. Cargar nodos - AirTAC-Booklet-EU-EN
LOAD CSV WITH HEADERS FROM 'file:///AirTAC-Booklet-EU-EN_nodes.csv' AS row
CREATE (n:DataNode)
SET n = row;

// 3. Cargar relaciones - AirTAC-Booklet-EU-EN
LOAD CSV WITH HEADERS FROM 'file:///AirTAC-Booklet-EU-EN_relationships.csv' AS row
MATCH (start:DataNode {id: row.start_id})
MATCH (end:DataNode {id: row.end_id})
CREATE (start)-[r:TIENE]->(end)
SET r.properties = row.properties;

// 4. Cargar nodos - AirTAC-Fitting-and-Tubing-Catalogue-PDF
LOAD CSV WITH HEADERS FROM 'file:///AirTAC-Fitting-and-Tubing-Catalogue-PDF_nodes.csv' AS row
CREATE (n:DataNode)
SET n = row;

// 5. Cargar relaciones - AirTAC-Fitting-and-Tubing-Catalogue-PDF
LOAD CSV WITH HEADERS FROM 'file:///AirTAC-Fitting-and-Tubing-Catalogue-PDF_relationships.csv' AS row
MATCH (start:DataNode {id: row.start_id})
MATCH (end:DataNode {id: row.end_id})
CREATE (start)-[r:TIENE]->(end)
SET r.properties = row.properties;

// 6. Cargar nodos - AirTAC-Product-Catalogue-EU-ES
LOAD CSV WITH HEADERS FROM 'file:///AirTAC-Product-Catalogue-EU-ES_nodes.csv' AS row
CREATE (n:DataNode)
SET n = row;

// 7. Cargar relaciones - AirTAC-Product-Catalogue-EU-ES
LOAD CSV WITH HEADERS FROM 'file:///AirTAC-Product-Catalogue-EU-ES_relationships.csv' AS row
MATCH (start:DataNode {id: row.start_id})
MATCH (end:DataNode {id: row.end_id})
CREATE (start)-[r:TIENE]->(end)
SET r.properties = row.properties;

// 8. Cargar nodos - Catalogo-AirTAC-INVIKTA-2016
LOAD CSV WITH HEADERS FROM 'file:///Catalogo-AirTAC-INVIKTA-2016_nodes.csv' AS row
CREATE (n:DataNode)
SET n = row;

// 9. Cargar relaciones - Catalogo-AirTAC-INVIKTA-2016
LOAD CSV WITH HEADERS FROM 'file:///Catalogo-AirTAC-INVIKTA-2016_relationships.csv' AS row
MATCH (start:DataNode {id: row.start_id})
MATCH (end:DataNode {id: row.end_id})
CREATE (start)-[r:TIENE]->(end)
SET r.properties = row.properties;

// 10. Cargar nodos - Linear-Guide-Catalogue-EU-ES
LOAD CSV WITH HEADERS FROM 'file:///Linear-Guide-Catalogue-EU-ES_nodes.csv' AS row
CREATE (n:DataNode)
SET n = row;

// 11. Cargar relaciones - Linear-Guide-Catalogue-EU-ES
LOAD CSV WITH HEADERS FROM 'file:///Linear-Guide-Catalogue-EU-ES_relationships.csv' AS row
MATCH (start:DataNode {id: row.start_id})
MATCH (end:DataNode {id: row.end_id})
CREATE (start)-[r:TIENE]->(end)
SET r.properties = row.properties;

// 12. Verificar conteos
MATCH (n:DataNode) RETURN count(n) as total_nodos;
MATCH ()-[r:TIENE]->() RETURN count(r) as total_relaciones;
