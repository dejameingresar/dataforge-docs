# DataForge NoSQL — documentación técnica

Sitio publicado en GitHub Pages: https://dejameingresar.github.io/dataforge-docs/

El flujo `.github/workflows/regenerar.yml` ejecuta `doc/publicar_docs.py` sobre el
código fuente versionado, copia el resultado a la raíz y lo publica en Pages.

---

# DataForge NoSQL

SI 783 Base de Datos II · Grupo 14 · Segundo avance de Unidad II

Rodriguez Cardenas, Patrick Elvis · Rios Cohaila, Nicole Luciana.

Completa datos de prueba desde una muestra y exporta a MongoDB, Redis,
Cassandra o Neo4j. El vocabulario neutral contiene 23 tipos; algunas
traducciones son aproximaciones, detalladas en doc/matriz-tipos.md.

## Ejecutar

**En la nube:** https://dataforge-nosql.vercel.app

Requiere Python 3.12 o superior. En Windows abrir Abrir-DataForge.cmd.

    python app.py

Abrir http://127.0.0.1:8000. Cargar ejemplo o archivo, revisar la estructura,
ajustar el total por coleccion, generar y exportar.
Los archivos exportados contienen los registros nuevos.
MongoDB acepta el arreglo con:

    mongoimport --db prueba --collection clientes --file clientes.json --jsonArray

## Segundo avance

- Sesion anonima por cookie HttpOnly y SameSite Lax, con vencimiento.
- Historial SQLite aislado por sesion y disponible en la pestaña Actividad.
- Cache LRU con TTL para catalogo y esquema de ejemplo.
- Log JSONL de metadatos y dashboard de llamadas, errores y tiempos.
- Respaldo consistente de la actividad, SHA256 y restauracion comprobada.
- Extension VS Code y habilidad local para el reto de integracion.

El servidor usa data/dataforge.sqlite3 y data/dataforge.jsonl.
DATAFORGE_DATOS permite elegir el directorio. No se persisten los cuerpos,
credenciales ni lotes del usuario. El modo web local no requiere drivers.
La escritura en motores vivos requiere el driver opcional y un destino elegido.

## Verificacion reproducible

    python -m pip install pymongo redis
    python tools/verificar_avance.py
    node --test integraciones/vscode/test/extension.test.js
    python doc/generar_documentos.py --verificar

12 comprobaciones superadas, 0 omitida(s), 0 fallidas. Ejecucion UTC: 2026-11-20T01:35:50+00:00.

Logs y JUnit: doc/reportes/avance2. Se distinguen suites, casos y pruebas con
proveedor simulado; no se suman como una sola cifra de cobertura.
La prueba Redis real requiere DATAFORGE_REDIS_TEST_PORT apuntando a una
instancia dedicada. No limpia bases ajenas.

## Base de datos y respaldos

    python db/aplicar_estado.py
    python db/backup_estado.py
    python dashboard/generar_dashboard.py

La base operativa tiene sesion y operacion, FK e indices. Su diccionario y
diagrama se generan desde el esquema SQLite real. El ejemplo de Liquibase
crea una proyeccion relacional de la tienda en PostgreSQL; es una demostracion
independiente y no se presenta como la base operativa del producto.
El ejercicio diario de CI se ejecuta sobre bases de prueba. El respaldo de
una instalacion real debe programarse sobre su directorio DATAFORGE_DATOS.

## Documentacion

- [FD05 del segundo avance](Documentos/FD05-Segundo-Avance-Unidad-II.md)
- [Adenda FD01 a FD04](Documentos/ADENDA-Unidad-II.md)
- [Estandar de programacion](doc/estandar-programacion.md)
- [Diccionario del ejemplo](doc/diccionario-datos.md)
- [Diccionario de actividad](doc/diccionario-estado.md)
- [Componentes](doc/arquitectura.svg)
- [Clases](doc/clases.svg)
- [Despliegue](doc/despliegue.svg)
- [Modelo del ejemplo](doc/modelo-er.svg)
- [Modelo de actividad](doc/estado-er.svg)
- [Matriz de rubrica](RUBRICA_BD2.md)
- [Guion de demostracion](expo/Segundo-avance.md)

    python doc/generar_documentos.py
    python doc/renderizar_diagramas.py --jar RUTA_A_PLANTUML.jar
    python tools/generar_readme.py
    python doc/publicar_docs.py

doc/_site contiene la referencia de clases, metodos y propiedades para Pages.
Los seis diagramas SVG se regeneran desde PlantUML. El README se genera con
este script a partir de las capacidades y del reporte real de pruebas.

## Automatizaciones

| Workflow | Resultado previsto |
| --- | --- |
| documentacion.yml | Suites, drivers, exportaciones y artefactos de evidencia |
| estado.yml | Objetos SQLite y ensayo de restauracion con reporte |
| liquibase.yml | Esquema de ejemplo sobre PostgreSQL real en CI |
| backups.yml | Restauracion y conteos de MongoDB y Redis de prueba |
| terraform.yml | Formato, validacion, plan simulado y costo estimado |
| release.yml | Pruebas, ZIP, SHA256, release y despliegue manual por hook |
| pages.yml | Publicacion de la referencia tecnica en GitHub Pages |

La validacion local de YAML no equivale a una ejecucion de GitHub.
El despliegue por hook requiere DEPLOY_HOOK y APP_URL en el entorno produccion.
Confirmar la revision que despliega el proveedor. El servicio gratuito de
Render usa almacenamiento efimero: para conservar historial se necesita un
volumen persistente. Terraform conserva actividad en /var/lib/dataforge.

## Infraestructura y costos

    terraform -chdir=terraform init -backend=false
    terraform -chdir=terraform validate
    terraform -chdir=terraform test

Las pruebas usan proveedor AWS simulado y no crean recursos. El despliegue real
requiere cuenta, estado persistente y autorizacion. Parametros: url_paquete
versionada, sha256_paquete, nombre_clave_ssh y cidr_administracion.
La descarga comprueba checksum; systemd inicia el proceso sin root.
El volumen se cifra, IMDSv2 es obligatorio y no se publican Redis ni MongoDB.

Costo base estimado: USD 11.88/mes para 730 horas de t3.micro, 8 GB gp3 y
una IPv4 publica, antes de creditos e impuestos. Detalle y fuentes en
doc/costos.md. No hay consumo AWS generado en este avance.

## Integracion del reto

Paquete: integraciones/vscode/dataforge-nosql-1.0.0.vsix.
En VS Code usar Extensions > Install from VSIX y abrir la raiz del proyecto.
Comandos: DataForge Iniciar servidor, Abrir aplicacion, Ejecutar pruebas.
La habilidad esta en integraciones/skill/dataforge/SKILL.md.
Las pruebas locales cubren la construccion de comandos; la activacion dentro
de VS Code y la instalacion en un agente deben demostrarse por separado.

## Limites

El detector infiere hasta 2000 registros por coleccion; inferir no confirma
restricciones que no aparecen en la muestra. Una semilla reproduce el lote con
los mismos parametros y version. No se han vuelto a ejecutar aqui los datasets
externos ni escrituras contra MongoDB, Cassandra o Neo4j vivos.
El servidor local de demostracion no incluye autenticacion de usuarios ni TLS.
Las sesiones anonimas no sustituyen un inicio de sesion. Antes de publicarlo
para usuarios externos se necesita proteger el acceso y los destinos de red.

La contribucion por integrante requiere el historial Git original. Esta copia
proviene de un ZIP y no contiene atribucion verificable de commits.
