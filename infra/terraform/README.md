# Terraform — `invoice-api-practice` (ECR + ECS Fargate)

> **Aviso importante**
> Esta configuración **nunca fue aplicada**. El autor de este repositorio no posee
> credenciales de AWS y jamás ejecutó `terraform apply` ni `terraform plan` contra
> una cuenta real. La configuración se valida localmente con `terraform validate`
> (que solo necesita el *schema* del provider, no credenciales).
> Aplicarla crea recursos **facturables**. Consulta la [tabla de riesgo de costo](#7-riesgo-de-costo)
> antes de hacer cualquier `apply`.

---

## 1. Qué es este directorio

`infra/terraform/` contiene la definición declarativa de la capa de infraestructura
de la API de facturas sobre AWS:

- Un repositorio **ECR** donde se publica la imagen Docker de la API.
- Un **cluster ECS** con una **task definition de Fargate** lista para correr el
  contenedor `invoice-api-practice:local` (o el `latest` publicado en ECR).
- Un **log group de CloudWatch Logs** con retención de 14 días.
- Los **roles IAM** mínimos que la task necesita para descargar la imagen y
  enviar los logs.

Lo que **no** incluye, y es deliberado: no hay VPC, ni subnets, ni NAT Gateway,
ni ALB (Application Load Balancer), ni RDS. Esas son justamente las piezas que
encarecen la factura. Esta es una base mínima y declarativa, suficiente para
mostrar el flujo de trabajo de Terraform como pieza de portfolio.

## 2. Estructura de archivos

| Archivo | Contenido |
|---|---|
| `versions.tf` | Versión de Terraform y versión del provider (`hashicorp/aws ~> 6.0`). |
| `providers.tf` | Configuración del provider `aws`, con `default_tags` globales. |
| `variables.tf` | Variables de entrada (`aws_region`, `project_name`, `environment`, `tags`, `container_cpu`, `container_memory`). |
| `locals.tf` | `name_prefix` y `common_tags`, derivados de las variables. |
| `ecr.tf` | Repositorio ECR y su política de ciclo de vida. |
| `ecs.tf` | Cluster ECS, rol de ejecución, log group y task definition de Fargate. |
| `outputs.tf` | Valores de salida (URL/ARN del ECR, nombre del cluster, ARN de la task, nombre del log group). |
| `backend.tf.example` | Plantilla de backend remoto S3. **No se usa automáticamente**: hay que copiarla a `backend.tf`. |

## 3. Comandos

Todos los comandos se ejecutan desde `infra/terraform/`.

### `terraform init` (local, sin backend)

```bash
cd infra/terraform
terraform init -backend=false -input=false
```

`-backend=false` fuerza el uso del backend local, así que la inicialización no
intenta conectarse a S3 ni a DynamoDB. Es el comando que usa el pipeline de CI.

### `terraform fmt`

```bash
terraform fmt -recursive       # formatea los archivos
terraform fmt -check -recursive # solo verifica; sale con código 1 si hay diferencias
```

### `terraform validate`

```bash
terraform validate
```

Valida la configuración contra el *schema* del provider. **No** requiere
credenciales de AWS y **no** crea ni modifica nada en la nube.

Salida esperada:

```text
Success! The configuration is valid.
```

### `terraform plan` (requiere credenciales)

```bash
terraform plan
```

Este comando **no se ejecutó nunca** en este repositorio: requiere credenciales
de AWS válidas y una cuenta con permisos de escritura. En una cuenta nueva,
`plan` muestra los recursos a crear.

> `terraform plan` y `terraform apply` están **desaconsejados** mientras este
> proyecto sea un ejercicio de portfolio sin una cuenta AWS dedicada. Revisa la
> sección 7 antes de ejecutarlos.

### `terraform destroy` (si llegaste a aplicar)

```bash
terraform destroy
```

Revisa la sección 7 antes de destruir: algunos recursos (logs, imágenes
almacenadas) generan cargos acumulativos que se siguen facturando un rato
después de la eliminación.

## 4. Habilitar el backend remoto

El estado remoto **no** está habilitado en este repositorio. `backend.tf` no
existe a propósito, así que Terraform usa el backend local y guarda el estado en
`terraform.tfstate`, dentro de esta misma carpeta.

Para activar el backend remoto (S3 + bloqueo con DynamoDB):

1. **Crear el bucket y la tabla a mano.** Este proyecto **nunca** los crea y no
   incluye código de Terraform para hacerlo: el bucket de estado debe existir
   *antes* del primer `terraform init` con backend, porque ese `init` lo necesita
   para guardar el estado. Créalos con la consola de AWS o con la CLI:

   ```bash
   # Bucket de estado (el nombre debe ser globalmente único)
   aws s3api create-bucket --bucket REPLACE_ME-your-terraform-state-bucket --region us-east-1
   aws s3api put-bucket-versioning --bucket REPLACE_ME-your-terraform-state-bucket \
     --versioning-configuration Status=Enabled
   aws s3api put-bucket-encryption --bucket REPLACE_ME-your-terraform-state-bucket \
     --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

   # Tabla de locks
   aws dynamodb create-table --table-name REPLACE_ME-your-terraform-locks-table \
     --region us-east-1 \
     --attribute-definitions AttributeName=LockID,AttributeType=S \
     --key-schema AttributeName=LockID,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST
   ```

2. **Copiar la plantilla y editar los placeholders:**

   ```bash
   cp backend.tf.example backend.tf
   $EDITOR backend.tf   # reemplazar REPLACE_ME-* por los nombres reales
   ```

3. **Re-inicializar con el backend remoto:**

   ```bash
   terraform init
   terraform init -migrate-state   # solo si ya existía estado local
   ```

4. **`backend.tf` es configuración local.** No contiene secretos (solo nombres
   de bucket y tabla), pero no debería versionarse: el estado remoto real se
   define con `-backend-config` o con un `backend.tf` local no commiteado. El
   proyecto lo mantiene fuera del repositorio; si se versiona por comodidad,
   agrega `backend.tf` a `.gitignore` antes de commitear.

## 5. Recursos que crea esta configuración

| Recurso | Tipo Terraform | Propósito |
|---|---|---|
| `<project>-<env>` | `aws_ecr_repository.app` | Repositorio de imágenes Docker (tags inmutables, escaneo en push). |
| — | `aws_ecr_lifecycle_policy.app` | Conserva las últimas 10 imágenes y expira las no etiquetadas a los 7 días. |
| `<project>-<env>` | `aws_ecs_cluster.main` | Cluster ECS (Fargate) con Container Insights deshabilitado. |
| `<project>-<env>-task-execution` | `aws_iam_role.task_execution` | Rol que asume `ecs-tasks.amazonaws.com`. |
| — | `aws_iam_role_policy.task_execution` | Política inline: logs, `ecr:GetAuthorizationToken` y descarga de capas de ECR. |
| `/ecs/<project>-<env>` | `aws_cloudwatch_log_group.app` | Logs del contenedor, con retención de 14 días. |
| `<project>-<env>` | `aws_ecs_task_definition.app` | Task definition de Fargate (256 CPU / 512 MiB) con healthcheck en `/health`. |

**No crea** y **no ejecuta**: VPC, subnets, NAT Gateway, Internet Gateway, ALB,
RDS/PostgreSQL, ni ninguna task en ejecución. La task definition existe, pero
**no hay ningún `aws_ecs_service`** que la levante: correr la API en AWS
requeriría primero una red (VPC + subnets) y una base de datos, y eso ya sale
del alcance de este ejercicio.

## 6. Variables de entrada

| Variable | Tipo | Default | Notas |
|---|---|---|---|
| `aws_region` | `string` | `us-east-1` | Región donde se crean los recursos. |
| `project_name` | `string` | `invoice-api-practice` | Prefijo de los nombres de recursos. |
| `environment` | `string` | `dev` | Validado: solo `dev`, `staging` o `prod`. |
| `tags` | `map(string)` | `{}` | Tags adicionales, mergeados sobre los comunes. |
| `container_cpu` | `number` | `256` | Unidades de CPU de Fargate. |
| `container_memory` | `number` | `512` | Memoria de la task en MiB. |

Tags comunes aplicados por `default_tags` y por cada recurso:
`Project`, `Environment`, `ManagedBy=terraform`.

## 7. Riesgo de costo

Aplicar esta configuración crea recursos que **se facturan**. No es un
desequilibrio de centavos, pero tampoco es un negocio: el mayor costo real de
una API en AWS casi nunca está en el ECR ni en los logs, está en la red.

| Recurso | ¿Cuesta dinero? | Costo aproximado |
|---|---|---|
| `aws_ecr_repository` | Solo si se guardan imágenes | Almacenamiento: **~USD 0.10 por GB-mes**. Una imagen de la API ronda los 150–250 MB, así que el costo real es de centavos. |
| `aws_ecr_lifecycle_policy` | No | Sin costo. Solo define reglas de expiración (que además **reducen** el costo de almacenamiento). |
| `aws_ecs_cluster` | No | Sin costo por el cluster en sí. |
| `aws_ecs_task_definition` | No | Registrar una task definition no se cobra. Solo se cobra cuando **corre** una task. |
| `aws_iam_role` + `aws_iam_role_policy` | No | Los roles IAM y las policies son gratuitos. |
| `aws_cloudwatch_log_group` | Solo por lo almacenado | Ingestión ~**USD 0.50 por GB** + retención ~**USD 0.03 por GB-mes**. Con retención de 14 días el costo es mínimo. |
| **Fargate (task en ejecución)** | **Sí, de forma continua** | ~**USD 0.04048 por vCPU-hora** y ~**USD 0.004445 por GB-hora**. Con 256 vCPU y 512 MiB: **~USD 0.012 por hora**, ~**USD 8.80 por mes** corriendo 24/7. **Una task que no corre no se cobra.** |
| VPC / subnets / NAT Gateway | **No incluidos** | Deliberadamente excluidos: el NAT Gateway cuesta ~**USD 32 por mes** más el tráfico, y un ALB ~**USD 16 por mes** más LCUs. Son las fuentes de costos sorpresa. |
| RDS / PostgreSQL | **No incluido** | Una instancia `db.t4g.micro` en Single-AZ cuesta ~**USD 15 por mes**. |

Puntos de control:

- Con esta configuración, **aplicarla y no correr ninguna task** cuesta
  centavos (unos pocos centavos de imágenes + logs). El riesgo financiero
  relevante aparece recién cuando se levanta una task de Fargate de forma
  continua o cuando se agrega una VPC con NAT Gateway.
- La `retention_in_days = 14` del log group acota el costo de logs.
- El ciclo de vida de ECR expira imágenes viejas, así que el almacenamiento no
  crece sin límite.
- Ten en cuenta que los cargos de AWS aparecen **con retraso**: borrar un
  recurso hoy no significa que mañana desaparezca de la factura.

## 8. Estado actual de esta configuración

- `terraform fmt -check -recursive` → limpio.
- `terraform init -backend=false -input=false` → correcto.
- `terraform validate` → `Success! The configuration is valid.`
- `terraform plan` → **nunca ejecutado** (requiere credenciales).
- `terraform apply` → **nunca ejecutado** (requiere credenciales). **No hay
  ningún recurso de AWS creado por este repositorio.**
- No existe `backend.tf` en el repositorio. Si se corre `terraform init` de
  forma local, aparece un `terraform.tfstate` que no debe commitearse.
