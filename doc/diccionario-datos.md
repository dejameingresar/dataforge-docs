# Diccionario de datos

Estructura detectada del ejemplo **Tienda en linea — MongoDB** (mongodb, formato JSON / JSONL).

La columna *Observado* es lo que el detector encontro en la muestra; *Generado* es lo que produce el motor a partir de esa observacion.

## Resumen

| Coleccion | Registros observados | Generados | Total | Campos |
| :- | -: | -: | -: | -: |
| `clientes` | 3 | 37 | 40 | 11 |
| `productos` | 2 | 38 | 40 | 9 |
| `pedidos` | 2 | 38 | 40 | 9 |

**120 registros en total** en 3 colecciones, con 100.0 % de completitud y 3/3 columnas unicas respetadas.

## `clientes`

3 registros observados en la muestra.

| Campo | Tipo neutral | Clave | Relacion | Dominio | Ejemplo observado |
| :- | :- | :- | :- | :- | :- |
| `_id` | objectid | PK |  |  | `6512a1f4c9e77b2d8a1f3e01` |
| `nombre` | nombre_persona |  |  |  | `Luis Rodriguez` |
| `email` | email |  |  |  | `luis.rodriguez@ejemplo.com` |
| `telefono` | telefono |  |  |  | `+51 987654321` |
| `ciudad` | ciudad |  |  |  | `Tacna` |
| `pais` | pais |  |  |  | `Peru` |
| `fecha_registro` | fecha |  |  |  | `2024-03-12` |
| `activo` | booleano |  |  |  | `true` |
| `nivel` | enum |  |  | 3 valores | `ORO` |
| `direccion` | mapa |  |  |  | `{"calle": "Av. Bolognesi 452", "di` |
| `etiquetas` | lista |  |  |  | `["frecuente", "mayorista"]` |

## `productos`

2 registros observados en la muestra.

| Campo | Tipo neutral | Clave | Relacion | Dominio | Ejemplo observado |
| :- | :- | :- | :- | :- | :- |
| `_id` | objectid | PK |  |  | `6512a1f4c9e77b2d8a2f3e01` |
| `sku` | sku |  |  |  | `SKU-10231` |
| `nombre` | producto |  |  |  | `Laptop 14 pulgadas` |
| `categoria` | enum |  |  | 2 valores | `Computo` |
| `precio` | flotante |  |  |  | `2499.9` |
| `moneda` | enum |  |  | 1 valores | `PEN` |
| `stock` | entero |  |  |  | `42` |
| `disponible` | booleano |  |  |  | `true` |
| `fecha_alta` | fecha |  |  |  | `2024-01-15` |

## `pedidos`

2 registros observados en la muestra.

| Campo | Tipo neutral | Clave | Relacion | Dominio | Ejemplo observado |
| :- | :- | :- | :- | :- | :- |
| `_id` | objectid | PK |  |  | `6512a1f4c9e77b2d8a3f3e01` |
| `numero` | texto |  |  |  | `PED-50001` |
| `id_cliente` | objectid |  | clientes |  | `6512a1f4c9e77b2d8a1f3e01` |
| `fecha` | fecha |  |  |  | `2025-06-14` |
| `estado` | enum |  |  | 2 valores | `ENTREGADO` |
| `total` | flotante |  |  |  | `3249.4` |
| `moneda` | enum |  |  | 1 valores | `PEN` |
| `items` | entero |  |  |  | `2` |
| `observacion` | descripcion |  |  |  | `Entregar en horario de oficina` |
