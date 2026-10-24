# Terraform — `invoice-api-practice` (ECR + ECS Fargate)

> **Aviso importante**
> Esta configuración **nunca fue aplicada contra una cuenta real de AWS**. El autor
> de este repositorio no posee credenciales de AWS y jamás ejecutó `terraform apply`
> ni `terraform plan` contra AWS.
>
> Lo que **sí** se hizo fue aplicarla contra **[Floci](https://floci.io/aws/)**, un
> emulador local de AWS que corre en Docker: los 33 recursos se crearon de verdad
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

**Red**

| Recurso | Tipo Terraform | Propósito |
|---|---|---|
| `10.0.0.0/16` | `aws_vpc.main` | VPC con DNS habilitado. |
| — | `aws_internet_gateway.main` | Salida a internet desde las subnets públicas. |
| 2 × públicas | `aws_subnet.public` | Una por zona de disponibilidad, con IP pública. |
| 2 × privadas | `aws_subnet.private` | Una por zona, sin IP pública: ahí corren las tasks. |
| — | `aws_nat_gateway.main` + `aws_eip.nat` | Salida a internet de las tasks (para pull de ECR). |
| 2 | `aws_route_table.*` + asociaciones | Rutas pública (IGW) y privada (NAT). |
| 3 | `aws_security_group.*` | ALB (público), tasks (solo del ALB) y base (solo de las tasks). |

**Aplicación**

| Recurso | Tipo Terraform | Propósito |
|---|---|---|
| `<project>-<env>` | `aws_ecr_repository.app` | Repositorio de imágenes Docker (tags inmutables, escaneo en push). |
| — | `aws_ecr_lifecycle_policy.app` | Conserva las últimas 10 imágenes y expira las no etiquetadas a los 7 días. |
| `<project>-<env>` | `aws_ecs_cluster.main` | Cluster ECS (Fargate) con Container Insights deshabilitado. |
| `<project>-<env>-task-execution` | `aws_iam_role.task_execution` | Rol que asume `ecs-tasks.amazonaws.com`. |
| — | `aws_iam_role_policy.task_execution` | Inline: logs, ECR y `secretsmanager:GetSecretValue`. |
| `/ecs/<project>-<env>` | `aws_cloudwatch_log_group.app` | Logs del contenedor, con retención de 14 días. |
| `<project>-<env>` | `aws_ecs_task_definition.app` | Task definition de la API (256 CPU / 512 MiB) con healthcheck en `/health`. |
| `<project>-<env>-migrate` | `aws_ecs_task_definition.migrate` | La misma imagen, pero corre `alembic upgrade head`. |
| `<project>-<env>-api` | `aws_ecs_service.api` | Mantiene las tasks corriendo y las registra en el target group. |

**Entrada**

| Recurso | Tipo Terraform | Propósito |
|---|---|---|
| `<project>-<env>` | `aws_lb.main` | Application Load Balancer en las subnets públicas. |
| `<project>-<env>-api` | `aws_lb_target_group.api` | Target group con health check en `/health`. |
| puerto 80 | `aws_lb_listener.http` | Reenvía todo al target group. |

**Datos y secretos**

| Recurso | Tipo Terraform | Propósito |
|---|---|---|
| `<project>-<env>-db` | `aws_db_subnet_group.main` | Subnets privadas donde vive la base. |
| `<project>-<env>-db` | `aws_db_instance.main` | PostgreSQL gestionado, no accesible desde internet. |
| `<project>-<env>/database` | `aws_secretsmanager_secret.database` | Credenciales de la base, como JSON. |
| — | `aws_secretsmanager_secret_version.database` | La versión con user, password, host, port y dbname. |

### El orden del despliegue

La API no puede arrancar contra una base sin esquema. El orden correcto es:

1. `terraform apply` — crea la infraestructura y registra las task definitions.
2. Correr la **task de migración** y esperar a que termine bien.
3. Mover el **service** a la task definition nueva.

```bash
aws ecs run-task --cluster <cluster> --task-definition <project>-<env>-migrate \
  --launch-type FARGATE --count 1 --network-configuration '...'
# esperá a que lastStatus sea STOPPED y exitCode 0

aws ecs update-service --cluster <cluster> --service <project>-<env>-api \
  --task-definition <project>-<env>
```

Migrar desde el entrypoint de la API sería un error: correría una migración por
réplica, y con un despliegue rolling eso son varias migraciones concurrentes.

## 6. Variables de entrada y ambientes

| Variable | Tipo | Default | Notas |
|---|---|---|---|
| `aws_region` | `string` | `us-east-1` | Región donde se crean los recursos. |
| `project_name` | `string` | `invoice-api-practice` | Prefijo de los nombres de recursos. |
| `environment` | `string` | **sin default (obligatoria)** | Validado: solo `dev`, `staging` o `prod`. Ver abajo. |
| `image_tag` | `string` | `latest` | Tag de la imagen. El repo ECR es inmutable, así que **tiene que cambiar en cada despliegue** (en un pipeline real, el SHA del commit). |
| `database_password` | `string` (sensitive) | **sin default (obligatoria)** | Contraseña de la base. Llega por `TF_VAR_database_password`. |
| `database_name` | `string` | `invoice` | Nombre de la base. |
| `database_username` | `string` | `invoice` | Usuario de la base. |
| `vpc_cidr` | `string` | `10.0.0.0/16` | CIDR de la VPC. |
| `availability_zones` | `list(string)` | `[us-east-1a, us-east-1b]` | Zonas de las subnets. |
| `public_subnet_cidrs` | `list(string)` | `[10.0.1.0/24, 10.0.2.0/24]` | CIDR de las subnets públicas. |
| `private_subnet_cidrs` | `list(string)` | `[10.0.11.0/24, 10.0.12.0/24]` | CIDR de las subnets privadas. |
| `app_port` | `number` | `8000` | Puerto del contenedor. |
| `service_desired_count` | `number` | `1` | Tasks que mantiene el service. |
| `rds_instance_class` | `string` | `db.t4g.micro` | Clase de la instancia. |
| `rds_allocated_storage` | `number` | `20` | Storage en GiB. |
| `rds_engine_version` | `string` | `16` | Versión de PostgreSQL. |
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

`database_password` es el ejemplo: está marcada como `sensitive = true` y **no**
aparece en ningún archivo commiteado. Se le pasa así:

```bash
export TF_VAR_database_password="una-password-que-no-sea-de-produccion"
terraform plan -var-file=environments/prod.tfvars
```

### Cómo llega el secreto al contenedor

La contraseña **no viaja en la task definition**. El flujo es:

```
Secrets Manager (JSON con user, password, host, port, dbname)
   │  el agente de ECS lo resuelve
   ▼
variable de entorno DATABASE_SECRET dentro del container
   │  la app parsea el JSON y arma la URL
   ▼
postgresql+psycopg://user:password@host:port/dbname
```

La app **no conoce AWS**: no tiene SDK de AWS, no pide permisos de IAM, no
sabe que existe un secret manager. Solo lee una variable de entorno y parsea un
JSON. Eso es el patrón "la plataforma resuelve el secreto" y es el que conviene
cuando corrés dentro de ECS.

El patrón alternativo —que la app sea cliente de Secrets Manager— tiene sentido
cuando el secreto tiene que rotar sin reiniciar el container, o cuando la app
corre fuera de ECS (Lambda, EC2, Kubernetes).

> **Limitación conocida de Terraform:** los valores de variables se guardan en el
> state file **en texto plano**, aunque estén marcados como `sensitive`. Por eso
> el secreto se construye acá desde una variable, y eso mete la contraseña en el
> state. En un proyecto real el secret se crea **fuera** de Terraform (a mano o
> con un pipeline de bootstrap) y Terraform solo referencia su ARN, así el state
> nunca tiene la contraseña. Está anotado en `secrets.tf`.

## 7. Riesgo de costo

Aplicar esta configuración crea recursos que **se facturan**. Y ahora la
configuración es completa: **no son centavos**. El costo real de una API en AWS
casi nunca está en la imagen ni en los logs: está en la red y en la base.

| Recurso | ¿Cuesta dinero? | Costo aproximado |
|---|---|---|
| **NAT Gateway** | **Sí, de forma continua** | **~USD 32 por mes** más el tráfico. Es el recurso más caro de toda la configuración. |
| **ALB** | **Sí, de forma continua** | **~USD 16 por mes** más las LCUs. |
| **RDS `db.t4g.micro`** | **Sí, de forma continua** | **~USD 15 por mes** en Single-AZ. |
| **Fargate (task en ejecución)** | **Sí, de forma continua** | ~**USD 0.012 por hora** con 256 vCPU y 512 MiB: **~USD 8.80 por mes** corriendo 24/7. **Una task que no corre no se cobra.** |
| ECR | Solo si se guardan imágenes | Almacenamiento: **~USD 0.10 por GB-mes**. Una imagen ronda los 150–250 MB, o sea centavos. |
| CloudWatch Logs | Solo por lo almacenado | Ingestión ~**USD 0.50 por GB** + retención ~**USD 0.03 por GB-mes**. |
| VPC, subnets, IGW, route tables, security groups | No | Los recursos de red en sí son gratuitos. |
| ECS cluster, task definitions, IAM roles, Secrets Manager | No | Registrar definiciones y roles no se cobra. |

**Total estimado con el stack completo corriendo 24/7: ~USD 72 por mes**
(~USD 32 NAT + ~USD 16 ALB + ~USD 15 RDS + ~USD 8.80 Fargate + centavos de
logs e imágenes).

Puntos de control:

- **Aplicarla y no correr nada** cuesta algunos centavos (imágenes y logs), pero
  el NAT Gateway, el ALB y el RDS **se facturan aunque no los uses**. Apagar la
  base o el balanceador no los elimina: hay que borrarlos.
- El NAT Gateway es el recurso más caro y el que más se olvida. La alternativa
  gratis son los **VPC endpoints** para ECR, S3 y CloudWatch Logs: con traffic
  privado no hace falta salir a internet.
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
  los 33 recursos, la task de migración corrió `alembic upgrade head` y la task
  de la API levantó el container, recibió el secreto y respondió `201`, `200`,
  `409` y `404` contra el RDS emulado. Ver la
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
# 1. Levantar el emulador
docker compose --profile aws-emulator up -d floci

# 2. Apuntar el provider de AWS al emulador
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_REGION=us-east-1

# 3. La contraseña de la base, que se usa para armar el secreto
export TF_VAR_database_password="una-password-de-prueba"

# 4. Estado separado del de AWS real
terraform init -reconfigure -backend-config="path=floci.tfstate"

# 5. Aplicar
terraform apply -auto-approve -var-file=environments/dev.tfvars -var image_tag=v1
```

El `AWS_ENDPOINT_URL` es la clave: el provider de AWS v6 lo respeta y redirige
todas las llamadas al emulador, sin tocar la configuración del provider.

> El paso 4 importa. El estado del emulador vive en `floci.tfstate` y el de AWS
> real en `terraform.tfstate`. Mezclarlos hace que Terraform crea que los
> recursos ya existen y falle con `RepositoryAlreadyExistsException`.

### Publicar la imagen

El repositorio ECR es **inmutable**, así que el tag tiene que cambiar en cada
despliegue. `latest` solo sirve para el primer despliegue.

```bash
# El registry de Floci corre en el puerto 5100 del host
docker buildx build \
  --output type=image,name=localhost:5100/000000000000/us-east-1/invoice-api-practice-dev:v1,compression=gzip,oci-mediatypes=false,push=true \
  .
```

Después hay que **actualizar la task definition** para que apunte al tag nuevo:

```bash
terraform apply -auto-approve -var-file=environments/dev.tfvars -var image_tag=v1
```

### El orden del despliegue, en el emulador

```bash
# 1. La migración, como task de una sola ejecución
aws ecs run-task --cluster invoice-api-practice-dev \
  --task-definition invoice-api-practice-dev-migrate --launch-type FARGATE --count 1 \
  --network-configuration 'awsvpcConfiguration={subnets=[...],securityGroups=[...]}'

# 2. Esperar a que termine con exitCode 0
# 3. La API
aws ecs update-service --cluster invoice-api-practice-dev \
  --service invoice-api-practice-dev-api --task-definition invoice-api-practice-dev
```

### Workarounds para bugs del emulador

Floci 2.1.0 tiene tres problemas que aparecen al usar el data plane de ECR. Se
documentan porque son genéricos (cualquier emulador los puede tener) y porque
encontrarlos es parte del ejercicio.

**1. La ruta del registry queda mal construida.** El proxy escribe el nombre del
repositorio con un carácter del tag pegado (`...-devatest` en vez de `...-dev`).
El camino correcto, que se puede ver en el catálogo del registry, es
`<cuenta>/<región>/<repositorio>`:

```bash
curl http://localhost:5100/v2/_catalog
# {"repositories":["000000000000/us-east-1/invoice-api-practice-dev"]}
```

Por eso la imagen se pushea **al registry directamente**, saltando el proxy.

**2. `registry:2` no entiende el formato de imagen que empuja Docker 29.** El
registry embebido es `registry:2` (2.8.3, de 2022) y su conversión a schema1
produce manifests rotos. Se resuelve generando el manifest con el formato
Docker clásico en vez de OCI, que es lo que hace el `--output` de `buildx` de
arriba (`compression=gzip,oci-mediatypes=false`).

**3. El registry queda huérfano si se recrea el stack.** Floci crea el
container del registry por su cuenta. Si el stack de compose se recrea
(`docker compose down`), ese container sobrevive atado a la red vieja y el
proxy de ECR responde `503` para siempre. La solución es borrarlo y dejar que
Floci lo vuelva a crear:

```bash
docker compose --profile aws-emulator down
docker rm -f floci-ecr-registry
docker compose --profile aws-emulator up -d floci
```

### Verificar que la task quedó sana

```bash
aws ecs list-tasks --cluster invoice-api-practice-dev --service-name invoice-api-practice-dev-api
docker ps | grep floci-ecs
```

Floci lanza un contenedor Docker real con la imagen del ECR. El contenedor
arranca la API con Uvicorn, queda `healthy` (el `HEALTHCHECK` del `Dockerfile`
le pega a `/health`) y sirve requests HTTP.

> **El detalle que solo aparece al probar de verdad:** `/health` hace `SELECT 1`,
> que funciona aunque **la tabla no exista**. El health check puede estar en
> verde mientras la API devuelve `500` al crear una factura. Por eso el
> despliegue tiene un paso aparte de migración: si te saltás ese paso, la
> infraestructura se ve perfecta y la aplicación está rota.
>
> En el emulador, el RDS corre como un Postgres real y la task lo alcanza por
> la red del compose. En AWS real, la task y el RDS están en la VPC.

### Lo que el emulador NO puede verificar

El proxy del ALB de Floci responde, pero **no reenvía el tráfico** al target
group: devuelve un 404 de Apache. Y la red emulada no implementa routing de
subnets ni NAT de verdad.

Lo que **sí** quedó verificado contra el emulador:

- Los 33 recursos se crean y el state los trackea.
- El backend remoto S3 + DynamoDB funciona (init, apply, state en el bucket).
- La task de migración corre `alembic upgrade head` y sale con código 0.
- La task de la API levanta el container, recibe `DATABASE_SECRET` resuelto,
  se conecta al RDS y responde `201`, `200`, `409` y `404`.

Lo que **no** se pudo verificar:

- Que el tráfico llegue a través del ALB (el proxy del emulador no reenvía).
- El comportamiento real de la VPC: NAT, rutas y security groups existen como
  recursos, pero el emulador no simula el filtrado de paquetes.

### Volver al estado de AWS real

```bash
terraform init -reconfigure
```

Esto vuelve a apuntar al backend `local` con `terraform.tfstate`. El estado del
emulador queda en `floci.tfstate`, que también está en `.gitignore`.
