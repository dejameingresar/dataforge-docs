# Estándar de programación

Versión del segundo avance de Unidad II, 19 de noviembre de 2026.

## Python

Python 3.12 o superior; UTF 8; cuatro espacios; nombres snake_case y clases
PascalCase. Separar adaptadores, inferencia y generación de la capa HTTP.
El núcleo de modo archivo depende de la biblioteca estándar. Los drivers
opcionales se cargan cuando se usan las conexiones.

Cada función pública explica su contrato. Las excepciones esperadas devuelven
un error legible. No convertir un fallo de prueba o despliegue en éxito.
Cerrar conexiones y archivos mediante context managers o finally.
Usar parámetros SQL; no concatenar datos del usuario dentro de consultas.

## Interfaz

JavaScript sin dependencias de ejecución. Tratar respuestas de la API como
datos; escapar texto antes de insertarlo en HTML. Conservar los volúmenes y la
semilla durante generación y exportación. Usar CSS adaptable y scroll dentro
de tablas y previsualizaciones, sin ensanchar el documento.

## Persistencia y observabilidad

Fechas UTC ISO 8601. Cookies de sesión con entropía criptográfica, HttpOnly y
SameSite Lax. Consultar historial por la sesión de la petición.
Registrar ruta, estado, duración y cantidades; excluir cuerpos y credenciales.
La retención y rotación del directorio de actividad deben configurarse en
cada instalación. No incluirlo en Git ni en paquetes.

## Verificación y entregas

Ejecutar tools/verificar_avance.py y conservar logs, resumen y JUnit.
Las pruebas con un motor real requieren instancia dedicada; no usar FLUSHALL.
Corregir regresiones con un caso observable. Separar evidencia local,
ejecución CI y despliegue publicado en los informes.

Empaquetar mediante tools/empaquetar.py. Incluir manifiesto SHA256 y verificar
el ZIP producido. Los cambios de documentación generada se realizan en su
generador. No fijar cifras de aprobación en la interfaz.
