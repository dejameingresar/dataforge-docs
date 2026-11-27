# Matriz de rúbrica — SI-783 Base de Datos II · Grupo 14

**Fuente:** Aula Virtual UPT, tareas *Proyecto de Unidad II* (`id=120900`) y *Proyecto de Unidad III* (`id=120901`), leídas en vivo el 27/11/2026. **Ambas usan exactamente la misma rúbrica: 13 criterios, 20 puntos.** El texto de los criterios y los niveles es literal de Moodle; el estado es verificación nuestra, no commenting del docente.

## Rúbrica literal

| # | Criterio | Niveles (puntos) | Máx. |
|---|---|---|---:|
| 1 | Problemática detallada y sustentada Objetivos medibles | Ninguno 0 · Parcial 0,5 · Completo 1 | 1 |
| 2 | Formatos FD01, FD02, FD03, FD04 | Ninguno 0 · Parcial 0,5 · Completo algunos 1 · Completo todos 2 | 2 |
| 3 | Codigo fuente de aplicación y base de datos en Github | Ninguno 0 · Parcial 1 · Completo 2 | 2 |
| 4 | Contribuciones al proyecto | Ninguno 0 · Menos del 40 % 0,5 · Entre 40 y 60 % 1 | 1 |
| 5 | Automatización en Github que genere la infraestructura Terraform. Debe incluir un reporte con los test superados. Debe incluir un reporte de los costos generados | Ninguno 0 · Parcial 1 · Completa 2 | 2 |
| 6 | Automatización en Github que configure los objetos de la base de datos utilizando por recomendacion Liquibase. y Genere el reporte correspondiente de ejecuciones. | Ninguno 0 · Parcial 0,5 · Completo 1 | 1 |
| 7 | Automatización en Github que realice la estrategia de copias de seguridad de la base de datos de su aplicación y Genere el reporte correspondiente. | Ninguno 0 · Parcial 1 · Completo 2 | 2 |
| 8 | Automatización en Github que genere el release y posteriormente el despliegue de la aplicación en la infraestructura aprovisionada | Ninguno 0 · Parcial 0,5 · Completo 1 | 1 |
| 9 | Automatización en Github que genere la documentación del proyecto en el archivo README.md Diccionario de Datos Diagrama de Entidad Relación de la base de datos Diagrama de Clases Diagrama de Componentes Diagrama de Despliegue | Ninguno 0 · Parcial 0,5 · Completo 1 | 1 |
| 10 | Automatización en Github que genere la documentación técnica del proyecto en Github Pages Detalle de cada clase, metodo propiedad | Ninguno 0 · Parcial 0,5 · Completo 1 | 1 |
| 11 | Presentación del Proyecto | Ninguno 0 · Parcial 1 · Completa 2 | 2 |
| 12 | Resolución de Preguntas y Discusiones | Ninguno 0 · Parcial 1 · Completa 2 | 2 |
| 13 | Dashboard de utilización del producto | Ninguno 0 · Parcial 1 · Completa 2 | 2 |
| | **Total** | | **20** |

## Estado actual y evidencia

| # | Evidencia existente | Estado |
|---|---|---|
| 1 | Adenda FD01–FD04: umbrales medibles, línea base reproducible, fuentes oficiales (Extended JSON, RESP, CQL, Cypher) | Listo |
| 2 | `Documentos/FD01…FD04` (PDF + DOCX), `Base/FD05…docx`, adenda en el PDF entregado | Listo |
| 3 | Repo classroom `UPT-FAING-EPIS/si783-2026-ii-proyecto-group-14`: `app.py`, `app/nucleo/`, `db/`, `terraform/`, `app/tests/` | Listo |
| 4 | `git shortlog`: 38 commits de Patrick (dos nombres de autor) y 1 de Nicole | **Pendiente** |
| 5 | `.github/workflows/terraform.yml` genera `reporte-pruebas.md` y `reporte-costes.md` como artefactos | Parcial: cifras contradictorias con `doc/costos.md` |
| 6 | `.github/workflows/liquibase.yml`, `db/liquibase/`, reporte `reporte-liquibase.md` como artefacto | Parcial: falta adjuntar el reporte en la entrega |
| 7 | `.github/workflows/backups.yml`, `db/copias/`, manifiesto y restauración probada | Parcial: hay un cambio sin commitear en `backups.yml` |
| 8 | `.github/workflows/release.yml` con hook manual; app viva en `dataforge-nosql.vercel.app` | Parcial: el PDF dice "sin ejecución remota verificada" |
| 9 | `doc/generar_documentos.py`, `doc/renderizar_diagramas.py`, 6 SVG y diccionarios | Listo |
| 10 | Pages publicado en `dejameingresar.github.io/dataforge-docs/`; `clases.html` incompleto y enlace roto a `RUBRICA_BD2.md` | Parcial |
| 11 | `expo/DataForge-Exposicion.pdf`, `Documentos/Guion-de-exposicion_BD.pdf` | Parcial: falta video de sustentación |
| 12 | Sin foros en BD2, sin comentarios en Moodle, sin discusiones en el repo | **Pendiente** |
| 13 | `dashboard/` publicado en surge.sh; `metricas.jsonl` con 4 eventos del 14/10 | Parcial: datos muy escasos y antiguo |

**Estimación actual: 13–15/20.** Entrega U2 enviada 6 días después del plazo y todavía *Sin calificar*.

## Plan U3 → 20/20

Vencimiento: 11–12 dic 2026. La rúbrica U3 es idéntica a la U2, así que **hay que volver a demostrar los 13 criterios**, no solo lo nuevo.

| # | Acción para el nivel "Completo" | Responsable |
|---|---|---|
| 1 | Copiar la adenda al FD05 de U3 y citar en él los umbrales medibles y sus fuentes | Patrick |
| 2 | Revisar FD01–FD04 con la adenda y generar FD05 U3 con fecha nueva | Grupo |
| 3 | Pegar en la entrega el enlace al repo classroom y el commit de cierre | Patrick |
| 4 | **No delegable:** Nicole debe hacer commits reales de trabajo propio hasta superar el 40 % de contribución. No cambiar autores de commits existentes | **Nicole** |
| 5 | Adjuntar `reporte-pruebas.md` y `reporte-costes.md`; unificar el costo en `doc/costos.md`, el README y el FD05 U3: **USD 0,64/mes con capa gratuita, USD 8,23/mes sin ella** (la IP elástica no se cobra si está asociada a instancia encendida) | Patrick |
| 6 | Adjuntar `reporte-liquibase.md` y el log de ejecución al FD05 U3 | Patrick |
| 7 | Commitear `backups.yml`, adjuntar `reporte-copias.md` y el manifiesto de restauración | Patrick |
| 8 | Demostrar despliegue real con URL, revision desplegada y salida del hook; quitar la frase "sin ejecución remota verificada" del FD05 U3 | Patrick |
| 9 | Verificar en CI los 6 artefactos generados (README, diccionario, ER, clases, componentes, despliegue) | Patrick |
| 10 | Regenerar Pages con el código fuente presente; publicar `clases.html` con las 4 clases del proyecto y `RUBRICA_BD2.md` | Patrick |
| 11 | Grabar video de sustentación de hasta 10 min y subirlo con el guion | Grupo |
| 12 | **No delegable:** participar de verdad en una pregunta/discusión del curso o del repo y guardar enlace o captura como evidencia | **Ambos** |
| 13 | Generar el dashboard con eventos reales recientes de la app desplegada y publicar el enlace | Patrick |

### Requisitos de la consigna U3 que NO puntúan en la rúbrica (pero bloquean "entrega completa")

- Video de explicación/venta de máximo 10 minutos.
- **50 videos de clientes** usando la aplicación, con enlaces accesibles sin login.

### Riesgos abiertos

- Entrega U2 fuera de fecha: el criterio actitudinal se pierde aunque la rúbrica llegue a 20.
- Sin retroalimentación escrita del docente en ninguna tarea: cualquier nota estimada es inferencia.
- `backups.yml` está modificado en el working tree; si no se commitea, el evaluator remoto no lo ve.
