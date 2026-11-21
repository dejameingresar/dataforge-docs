# Diccionario de la base de actividad

Derivado de los objetos SQLite que crea AlmacenEstado.

## sesion

| Campo | Tipo | Nulo | PK |
| --- | --- | --- | --- |
| id | TEXT | no | si |
| creada_utc | TEXT | no |  |
| ultima_actividad_utc | TEXT | no |  |
| vence_epoch | INTEGER | no |  |

## operacion

| Campo | Tipo | Nulo | PK |
| --- | --- | --- | --- |
| id | INTEGER | no | si |
| sesion_id | TEXT | no |  |
| fecha_utc | TEXT | no |  |
| ruta | TEXT | no |  |
| estado | INTEGER | no |  |
| duracion_ms | INTEGER | no |  |
| registros | INTEGER | no |  |
| motor | TEXT | si |  |
| cache_hit | INTEGER | no |  |
