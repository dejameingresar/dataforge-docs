# Costos de infraestructura

Estimación de referencia consultada el 17 de noviembre de 2026.
Región us east 1, Linux, 730 horas por mes. No se creó infraestructura AWS.

| Concepto | Operación | USD por mes |
| --- | --- | ---: |
| EC2 t3.micro | 730 × 0.0104 | 7.592 |
| gp3 8 GB | 8 × 0.08 | 0.640 |
| IPv4 pública | 730 × 0.005 | 3.650 |
| Total base redondeado | | 11.88 |

No incluye transferencia adicional, snapshots, impuestos ni servicios
añadidos. No se descuentan créditos de una cuenta nueva. El costo real debe
contrastarse con Billing de la cuenta y su región. No hay factura ni gasto
generado por este trabajo.

Fuentes de precios: [EC2 T3](https://aws.amazon.com/ec2/instance-types/t3/),
[gp3](https://aws.amazon.com/ebs/general-purpose/),
[IPv4 pública](https://aws.amazon.com/vpc/pricing/).
Las condiciones de créditos se consultan en [AWS Free Tier](https://aws.amazon.com/free/).
