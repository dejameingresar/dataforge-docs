# Matriz de compatibilidad de tipos

El proyecto declara su esquema en un **vocabulario neutral** de 23 tipos. Cada adaptador lo traduce al tipo nativo de su motor, y esta tabla se genera leyendo esa traduccion: no se escribe a mano, de modo que no puede quedar desactualizada.

**nativo** = el motor tiene un tipo propio para ese valor.  
**aprox.** = el motor no lo tiene y lo guarda como texto (el caso de Redis, que solo almacena cadenas).

## Cobertura por motor

| Motor | Familia | Tipos nativos | Aproximados | Cobertura |
| :- | :- | -: | -: | -: |
| **MongoDB** | documental | 21 | 2 | 91 % |
| **Redis** | clave-valor | 7 | 16 | 30 % |
| **Cassandra** | columnar | 22 | 1 | 96 % |
| **Neo4j** | grafos | 19 | 4 | 83 % |

## Traduccion tipo por tipo

| Tipo neutral | MongoDB | Redis | Cassandra | Neo4j |
| :- | :- | :- | :- | :- |
| `objectid` | `ObjectId` | `string` *(aprox.)* | `uuid` | `String` *(aprox.)* |
| `uuid` | `BinData (subtype 4)` | `string` *(aprox.)* | `uuid` | `String` *(aprox.)* |
| `texto` | `string` | `string` | `text` | `String` |
| `texto_largo` | `string` | `string` | `text` | `String` |
| `email` | `string` | `string` | `text` | `String` |
| `telefono` | `string` | `string` | `text` | `String` |
| `url` | `string` | `string` | `text` | `String` |
| `dni` | `string` | `string` | `text` | `String` |
| `entero` | `int` | `string` *(aprox.)* | `int` | `Integer` |
| `largo` | `long` | `string` *(aprox.)* | `bigint` | `Integer` |
| `decimal` | `Decimal128` | `string` *(aprox.)* | `decimal` | `Float` |
| `flotante` | `double` | `string` *(aprox.)* | `double` | `Float` |
| `booleano` | `bool` | `string` *(aprox.)* | `boolean` | `Boolean` |
| `fecha` | `date` | `string` *(aprox.)* | `date` | `Date` |
| `fecha_hora` | `date` | `string` *(aprox.)* | `timestamp` | `DateTime` |
| `hora` | `string` *(aprox.)* | `string` *(aprox.)* | `time` | `Time` |
| `timestamp` | `timestamp` | `string` *(aprox.)* | `timestamp` | `Integer` |
| `enum` | `string` | `string` | `text` | `String` |
| `lista` | `array` | `string (JSON)` *(aprox.)* | `list<text>` | `List` |
| `mapa` | `object` | `string (JSON)` *(aprox.)* | `map<text, text>` | `Map` |
| `binario` | `binData` | `string (base64)` *(aprox.)* | `blob` | `String (base64)` *(aprox.)* |
| `geo` | `GeoJSON point` | `string (JSON)` *(aprox.)* | `text` *(aprox.)* | `Point` |
| `inet` | `string` *(aprox.)* | `string` *(aprox.)* | `inet` | `String` *(aprox.)* |

## Tipos que cada motor tiene que aproximar

### MongoDB

| Tipo neutral | Se guarda como |
| :- | :- |
| `hora` | `string` |
| `inet` | `string` |

### Redis

| Tipo neutral | Se guarda como |
| :- | :- |
| `objectid` | `string` |
| `uuid` | `string` |
| `entero` | `string` |
| `largo` | `string` |
| `decimal` | `string` |
| `flotante` | `string` |
| `booleano` | `string` |
| `fecha` | `string` |
| `fecha_hora` | `string` |
| `hora` | `string` |
| `timestamp` | `string` |
| `lista` | `string (JSON)` |
| `mapa` | `string (JSON)` |
| `binario` | `string (base64)` |
| `geo` | `string (JSON)` |
| `inet` | `string` |

### Cassandra

| Tipo neutral | Se guarda como |
| :- | :- |
| `geo` | `text` |

### Neo4j

| Tipo neutral | Se guarda como |
| :- | :- |
| `objectid` | `String` |
| `uuid` | `String` |
| `binario` | `String (base64)` |
| `inet` | `String` |
