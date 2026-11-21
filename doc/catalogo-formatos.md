# Formatos de entrada y salida

## Lo que cada motor acepta como entrada

| Motor | Formatos que el detector reconoce |
| :- | :- |
| **MongoDB** | Arreglo JSON · JSONL de `mongoexport` · objeto con una clave por coleccion · cualquier JSON con la forma inferible |
| **Redis** | Comandos `HSET` · volcado en protocolo RESP · JSON de clave → objeto |
| **Cassandra** | DDL `CREATE TABLE ... (...)` · filas en CSV con cabecera |
| **Neo4j** | Sentencias Cypher `CREATE (:Etiqueta {...})` · JSON de nodos |

## Lo que produce cada motor como salida

| Motor | Formato | Archivo | Como se carga |
| :- | :- | :- | :- |
| MongoDB | Documentos JSON (mongoimport) | `.json` | `mongoimport --db X --collection Y --file Y.json` |
| MongoDB | Script de mongosh (insertMany) | `.json` | `mongoimport --db X --collection Y --file Y.json` |
| Redis | Comandos RESP (redis-cli --pipe) | `.redis` | `redis-cli --pipe < archivo.resp` |
| Redis | Comandos en texto (HSET) | `.redis` | `redis-cli --pipe < archivo.resp` |
| Cassandra | DDL + INSERT para cqlsh | `.cql` | `cqlsh -f archivo.cql`  ·  `COPY tabla FROM 'x.csv'` |
| Cassandra | CSV para COPY FROM | `.cql` | `cqlsh -f archivo.cql`  ·  `COPY tabla FROM 'x.csv'` |
| Neo4j | Sentencias Cypher (CREATE) | `.cypher` | Pegar en Neo4j Browser  ·  `cypher-shell -f archivo.cypher` |
| Neo4j | CSV para LOAD CSV | `.cypher` | Pegar en Neo4j Browser  ·  `cypher-shell -f archivo.cypher` |

## Diferencias de carga entre motores

| Aspecto | MongoDB | Redis | Cassandra | Neo4j |
| :- | :- | :- | :- | :- |
| **Unidad de datos** | documento | clave (hash) | fila | nodo |
| **Identificador** | `_id` (ObjectId) | nombre de la clave | clave de particion | propiedad `id` |
| **Relacion entre datos** | campo con la clave | clave con prefijo | clave de particion | arista |
| **Carga masiva** | `mongoimport` | `--pipe` | `COPY` | `LOAD CSV` |
| **Tipo de los valores** | BSON | cadena | CQL | propiedad tipada |
