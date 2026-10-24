# Terraform — `invoice-api-practice` (ECR + ECS Fargate)

> **Aviso importante**
> Esta configuración **nunca fue aplicada contra una cuenta real de AWS**. El autor
> de este repositorio no posee credenciales de AWS y jamás ejecutó `terraform apply`
> ni `terraform plan` contra AWS.
>
> Lo que **sí** se hizo fue aplicarla contra **[Floci](https://floci.io/aws/)**, un
> emulador local de AWS que corre en Docker: los 7 recursos se crearon de verdad
> contra una API compatible con AWS, y una task de ECS llegó a levantar el
> contenedor de la API. Ver [Practicar localmente con Floci](#9-practicar-localmente-con-floci).
>
> Aplicarla contra AWS real crea recursos **facturables**. Consulta la
> [tabla de riesgo de costo](#7-riesgo-de-costo) antes de hacer cualquier `apply`.

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
| `versions.tf` | Versión de Terraform, versión del provider (`hashicorp/aws ~> 6.0`) y el bloque `backend "local"`. |
| `providers.tf` | Configuración del provider `aws`, con `default_tags` globales. |
| `variables.tf` | Variables de entrada. `environment` y `database_url` son **obligatorias y sin default**, a propósito. |
| `locals.tf` | `name_prefix` y `common_tags`, derivados de las variables. |
| `ecr.tf` | Repositorio ECR y su política de ciclo de vida. |
| `ecs.tf` | Cluster ECS, rol de ejecución, log group y task definition de Fargate. |
| `outputs.tf` | Valores de salida (URL/ARN del ECR, nombre del cluster, ARN de la task, nombre del log group). |
| `environments/*.tfvars` | Un archivo por ambiente (`dev`, `staging`, `prod`) con los valores de cada uno. |
| `tests/environments.tftest.hcl` | Tests de Terraform (`terraform test`), offline y sin credenciales. |
| `backend.tf.example` | Plantilla de backend remoto S3 (AWS real). **No se usa automáticamente**: hay que reemplazarla por el bloque `backend "local"` de `versions.tf`. |
| `backend.floci.example` | La misma idea apuntando al emulador local (endpoints + credenciales falsas). |

## 3. Comandos

Todos los comandos se ejecutan desde `infra/terraform/`.

### `terraform init` (local, sin backend)

```bash
cd infra/terraform
terraform init -input=false
```

Como el backend local está declarado de forma explícita en `versions.tf`, este
`init` no toca S3 ni DynamoDB: solo descarga el provider y prepara el backend
local. Es el comando que usa el pipeline de CI y **no requiere credenciales**.

> Si en algún momento se activa el backend remoto (sección 4), `terraform init`
> va a intentar conectarse a S3. En ese caso, `-backend=false` sirve para
> inicializar sin tocar el backend remoto, pero deja el resto de comandos
> sin poder ejecutarse.

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
terraform plan -var-file=environments/dev.tfvars
```

Requiere credenciales de AWS válidas y una cuenta con permisos de escritura.
Contra AWS real **nunca se ejecutó** en este repositorio; contra el emulador
local de la [sección 9](#9-practicar-localmente-con-floci) sí.

> `terraform plan` y `terraform apply` están **desaconsejados** mientras este
> proyecto sea un ejercicio de portfolio sin una cuenta AWS dedicada. Revisa la
> sección 7 antes de ejecutarlos.

### `terraform test` (offline, sin credenciales)

```bash
terraform test
```

Ejecuta los tests de `tests/environments.tftest.hcl`. Usan `mock_provider`, así
que el provider de AWS es reemplazado por uno falso que **no hace ninguna
llamada a la API**: no hay credenciales, ni cuenta, ni costo. Lo que se verifica
es el *plan* — que cada ambiente produzca los nombres correctos y que la task
definition pase el `DATABASE_URL` al contenedor.

Salida esperada:

```text
Success! 4 passed, 0 failed.
```

### `terraform destroy` (si llegaste a aplicar)

```bash
terraform destroy -var-file=environments/dev.tfvars
```

Revisa la sección 7 antes de destruir: algunos recursos (logs, imágenes
almacenadas) generan cargos acumulativos que se siguen facturando un rato
después de la eliminación.

## 4. Habilitar el backend remoto

El estado remoto **no** está habilitado en este repositorio. `backend.tf` no
existe a propósito, así que Terraform usa el backend local declarado en
`versions.tf`:

```hcl
backend "local" {
  path = "terraform.tfstate"
}
```

El bloque está declarado de forma explícita (en vez de usar el backend local
implícito) por un motivo concreto: permite redirigir el estado a otro archivo
con `terraform init -backend-config="path=..."`, que es lo que hace el emulador
local de la [sección 9](#9-practicar-localmente-con-floci) para no mezclar su
estado con el de una despliegue real.

Para activar el backend remoto (S3 + bloqueo con DynamoDB), hay que
**reemplazar** ese bloque por el de `backend.tf.example` (Terraform solo
admite un bloque `backend` en toda la configuración) y luego:

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

### Practicar el backend remoto sin AWS

El mismo flujo se puede practicar entero contra el emulador local, porque
Floci implementa S3 y DynamoDB de verdad. `backend.floci.example` tiene la
configuración lista (con el argumento `endpoints`, que en el backend S3 actual
es un argumento y no un bloque):

```bash
# 1. Crear el bucket y la tabla en el emulador
aws s3 mb s3://invoice-tf-state
aws dynamodb create-table --table-name invoice-tf-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

# 2. Usar ese backend en vez del local
cp backend.floci.example backend.tf

# 3. Inicializar y aplicar
terraform init -input=false
terraform apply -auto-approve -var-file=environments/dev.tfvars

# 4. El estado quedó en S3, no en el disco
aws s3 ls s3://invoice-tf-state/ --recursive
# 2026-10-24 09:47:14  13308  invoice-api-practice/dev/terraform.tfstate
```

Esto ya está verificado: el `init` inicializa el backend contra el emulador, el
`apply` crea los recursos y el state file termina en el bucket de S3 con la
tabla de DynamoDB haciendo de lock.

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

## 6. Variables de entrada y ambientes

| Variable | Tipo | Default | Notas |
|---|---|---|---|
| `aws_region` | `string` | `us-east-1` | Región donde se crean los recursos. |
| `project_name` | `string` | `invoice-api-practice` | Prefijo de los nombres de recursos. |
| `environment` | `string` | **sin default (obligatoria)** | Validado: solo `dev`, `staging` o `prod`. Ver abajo. |
| `database_url` | `string` (sensitive) | **sin default (obligatoria)** | Connection string del contenedor. Llega por `TF_VAR_database_url`. |
| `tags` | `map(string)` | `{}` | Tags adicionales, mergeados sobre los comunes. |
| `container_cpu` | `number` | `256` | Unidades de CPU de Fargate. |
| `container_memory` | `number` | `512` | Memoria de la task en MiB. |

Tags comunes aplicados por `default_tags` y por cada recurso:
`Project`, `Environment`, `ManagedBy=terraform`.

### Un archivo por ambiente

Los valores de cada ambiente viven en `environments/`:

| Archivo | `environment` | `container_cpu` / `container_memory` | Tags |
|---|---|---|---|
| `environments/dev.tfvars` | `dev` | 256 / 512 | `Owner` |
| `environments/staging.tfvars` | `staging` | 256 / 512 | `Owner`, `CostCenter` |
| `environments/prod.tfvars` | `prod` | 512 / 1024 | `Owner`, `CostCenter`, `Compliance` |

```bash
terraform plan -var-file=environments/staging.tfvars
```

`environment` **no tiene default a propósito**. Con un default, un
`terraform plan` sin `--var-file` apuntaría silenciosamente a `dev`, y el error
más caro de esta configuración no es de sintaxis: es **desplegar el ambiente
equivocado**. Al ser obligatoria, el comando falla:

```text
Error: No value for required variable
```

### La regla de los secretos

| Tipo de valor | Dónde va | ¿Se commitea? |
|---|---|---|
| Valores que no son secretos (región, ambiente, tags, tamaño) | `environments/*.tfvars` | Sí |
| Secretos (passwords, connection strings) | Variable de entorno `TF_VAR_<nombre>` | No |

`database_url` es el ejemplo: está marcada como `sensitive = true` y **no**
aparece en ningún archivo commiteado. Se le pasa así:

```bash
export TF_VAR_database_url="postgresql+psycopg://user:password@host:5432/invoice"
terraform plan -var-file=environments/prod.tfvars
```

> **Limitación conocida de Terraform:** los valores de variables se guardan en el
> state file **en texto plano**, aunque estén marcados como `sensitive`. Por eso
> un proyecto real debería leer el secreto desde **Secrets Manager** dentro de la
> task definition, en vez de pasarlo como variable. Está anotado en
> `variables.tf` y es una de las limitaciones que más se preguntan en una
> entrevista sobre IaC.

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
- `terraform init -input=false` → correcto.
- `terraform validate` → `Success! The configuration is valid.`
- `terraform test` → `Success! 4 passed, 0 failed.` (offline, sin credenciales).
- `terraform plan` contra **AWS real** → **nunca ejecutado** (requiere credenciales).
- `terraform apply` contra **AWS real** → **nunca ejecutado** (requiere credenciales).
  **No hay ningún recurso de AWS creado por este repositorio.**
- `terraform apply` contra **Floci** (emulador local) → **ejecutado**: se crearon
  los 7 recursos y una task de ECS levantó el contenedor de la API. Ver la
  [sección 9](#9-practicar-localmente-con-floci).
- No existe `backend.tf` en el repositorio. Si se corre `terraform init` de
  forma local, aparece un `terraform.tfstate` que no debe commitearse.

## 9. Practicar localmente con Floci

[Floci](https://floci.io/aws/) es un emulador de AWS libre y MIT-licensed que
corre en Docker. No es un mock: implementa las APIs de AWS de verdad, y para
algunos servicios corre el motor real (el registry de ECR es un `registry:2`
OCI, y ECS lanza contenedores Docker reales).

Esto permite **aplicar la infraestructura completa sin cuenta de AWS y sin
costo**, que es exactamente lo que hace falta para practicar sin abrir la
cartera.

### Puesta en marcha

El emulador es un servicio del `docker-compose.yml` del proyecto, detrás de un
profile para que no arranque con el stack normal:

```bash
# 1. Levantar el emulador (y Postgres, que la task necesita)
docker compose --profile aws-emulator up -d floci postgres

# 2. Apuntar el provider de AWS al emulador
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_REGION=us-east-1

# 3. La base que va a ver el contenedor de la task: la IP del host en la red
#    bridge, porque el contenedor de ECS no comparte red con el compose.
HOST_IP=$(docker network inspect bridge --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}')
export TF_VAR_database_url="postgresql+psycopg://invoice:invoice@${HOST_IP}:5433/invoice"

# 4. Estado separado del de AWS real
terraform init -reconfigure -backend-config="path=floci.tfstate"

# 5. Aplicar
terraform apply -auto-approve -var-file=environments/dev.tfvars
```

El `AWS_ENDPOINT_URL` es la clave: el provider de AWS v6 lo respeta y redirige
todas las llamadas al emulador, sin tocar la configuración del provider.

> El paso 3 importa. El estado del emulador vive en `floci.tfstate` y el de AWS
> real en `terraform.tfstate`. Mezclarlos hace que Terraform crea que los
> recursos ya existen y falle con `RepositoryAlreadyExistsException`.

### Workarounds para bugs del emulador

Floci 2.1.0 tiene dos problemas que aparecen al usar el data plane de ECR. Se
documentan porque son genéricos (cualquier emulador los puede tener) y porque
encontrarlos es parte del ejercicio.

**1. El proxy de ECR no encuentra su propio registry.** Floci crea el container
del registry y después intenta conectarlo a la red `bridge`, pero Docker ya lo
autoconectó, así que el alias de red no se registra y el proxy responde `503`.
Se arregla apuntando el nombre del registry a su IP dentro del contenedor de
Floci:

```bash
REG_IP=$(docker inspect floci-ecr-registry --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
docker exec --user root floci sh -c "echo '$REG_IP floci-ecr-registry' >> /etc/hosts"
```

**2. La ruta del registry queda mal construida.** El proxy escribe el nombre del
repositorio con un carácter del tag pegado (`...-devatest` en vez de `...-dev`).
El camino correcto, que se puede ver en el catálogo del registry, es
`<cuenta>/<región>/<repositorio>`:

```bash
curl http://localhost:5100/v2/_catalog
# {"repositories":["000000000000/us-east-1/invoice-api-practice-dev"]}

docker tag invoice-api-practice-api:latest \
  "localhost:5100/000000000000/us-east-1/invoice-api-practice-dev:latest"
docker push "localhost:5100/000000000000/us-east-1/invoice-api-practice-dev:latest"
```

**3. `registry:2` no entiende el formato de imagen que empuja Docker 29.** El
registry embebido es `registry:2` (2.8.3, de 2022) y su conversión a schema1
produce manifests rotos. Se resuelve generando el manifest con el formato
Docker clásico en vez de OCI:

```bash
docker buildx build \
  --output type=image,name=localhost:5100/000000000000/us-east-1/invoice-api-practice-dev:latest,compression=gzip,oci-mediatypes=false,push=true \
  .
```

### Correr la task

```bash
aws ecs run-task \
  --cluster invoice-api-practice-dev \
  --task-definition invoice-api-practice-dev:1 \
  --launch-type FARGATE \
  --count 1 \
  --network-configuration 'awsvpcConfiguration={subnets=[subnet-default-us-east-1-a],securityGroups=[sg-default]}'
```

Floci lanza un contenedor Docker real con la imagen del ECR. El contenedor
arranca la API con Uvicorn, queda `healthy` (el `HEALTHCHECK` del `Dockerfile`
le pega a `/health`) y sirve requests HTTP.

> La base de datos tiene que ser alcanzable desde el contenedor: el `DATABASE_URL`
> apunta a la IP del host en la red bridge, no al nombre `postgres` de un
> compose. Si el `HEALTHCHECK` devuelve `degraded`, la base no está a mano.
>
> Un detalle que aparece solo al probar de verdad: `/health` hace `SELECT 1`, que
> funciona aunque **la tabla no exista**. El health check puede estar en verde
> mientras la API devuelve `500` al crear una factura. El esquema hay que
> aplicarlo: `uv run alembic upgrade head`.

### Volver al estado de AWS real

```bash
terraform init -reconfigure
```

Esto vuelve a apuntar al backend `local` con `terraform.tfstate`. El estado del
emulador queda en `floci.tfstate`, que también está en `.gitignore`.
