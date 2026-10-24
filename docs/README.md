# Documentación

| Documento | Para qué |
|---|---|
| [`terraform-guide.md`](terraform-guide.md) | Qué es Terraform y cómo se trabaja con él **en producción**. Pensada para quien nunca aplicó Terraform en un ambiente real. |
| [`../infra/terraform/README.md`](../infra/terraform/README.md) | Referencia del directorio de infraestructura: qué hace cada archivo, qué comandos correr, cuánto cuesta y cómo practicarlo localmente. |
| [`../README.md`](../README.md) | El overview del proyecto: arquitectura, decisiones y preguntas de entrevista. |

## Orden de lectura sugerido

1. El [README del proyecto](../README.md), para entender qué es y qué problema resuelve.
2. `terraform-guide.md`, **si la parte de infraestructura es nueva para vos**. Explica el modelo mental, el flujo real de un apply en producción, los conceptos que solo importan cuando hay un equipo, y los errores clásicos.
3. El [README de infra](../infra/terraform/README.md), como referencia operativa.

La guía y la referencia responden preguntas distintas y están separadas a
propósito: la guía se lee de corrido, la referencia se consulta.
