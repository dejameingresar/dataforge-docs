# Costos de infraestructura

Estimación de referencia consultada el 17 de noviembre de 2026.
Región us-east-1, Linux, 730 horas por mes. No se creó infraestructura AWS.

| Concepto | Operación | USD por mes (sin capa gratuita) |
| --- | --- | ---: |
| EC2 t3.micro | 730 × 0.0104 | 7.592 |
| gp3 8 GB | 8 × 0.080 | 0.640 |
| IPv4 pública asociada a instancia encendida | 730 × 0.000 | 0.000 |
| **Total** | | **8.232 ≈ 8.23** |

Con la capa gratuita vigente (750 h/mes de t3.micro durante los primeros 12
meses) la EC2 cuesta 0 y el total es **0.64 USD por mes**, solo el disco.

La IPv4 pública se cobra unos 0.005 USD/hora **solo cuando está sin asociar o
asociada a una instancia apagada**. El diseño la mantiene asociada a la
instancia encendida, por eso no entra en el total. La cifra de 11.88 USD que
aparecía en versiones anteriores contaba esa IP como si estuviera ociosa y
queda corregida por esta tabla.

Este desglose coincide con el `reporte-costes.md` que genera
`.github/workflows/terraform.yml` en cada ejecución.

No incluye transferencia adicional, snapshots, impuestos ni servicios
añadidos. El costo real debe contrastarse con Billing de la cuenta y su
región. No hay factura ni gasto generado por este trabajo.

Fuentes de precios: [EC2 T3](https://aws.amazon.com/ec2/instance-types/t3/),
[gp3](https://aws.amazon.com/ebs/general-purpose/),
[IPv4 pública](https://aws.amazon.com/vpc/pricing/).
Las condiciones de créditos se consultan en [AWS Free Tier](https://aws.amazon.com/free/).
