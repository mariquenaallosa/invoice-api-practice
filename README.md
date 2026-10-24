# invoice-api-practice

API REST para gestionar facturas, construida como **pieza de portfolio para practicar
entrevistas técnicas de Full Stack Engineer con foco en Python**.

No es un producto ni un proyecto de cliente. Es un dominio acotado —facturas— elegido
porque permite demostrar el camino completo de un servicio real sin agregar complejidad
artificial: capa de datos, reglas de negocio, validación, manejo de errores, tests,
contenedores, pipeline e infraestructura declarativa.

---

## 1. Qué problema resuelve

Una API de facturas es un problema que todo el mundo entiende y que tiene las piezas
justas para discutir en una entrevista:

- Modelo de dominio con dinero, fechas y estados.
- Unicidad de negocio que tiene que estar garantizada por la base, no solo por Python.
- Códigos HTTP que un cliente puede usar para decidir qué hacer.
- Errores consistentes, porque un cliente que parsea dos formatos distintos rompe.
- Datos que hay que poder crear, leer y paginar sin duplicar ni perder.

El objetivo no es "una API de facturas". Es poder responder con criterio y con código
**"¿por qué lo hiciste así?"** en cada decisión.

---

## 2. Arquitectura

El proyecto separa estrictamente **HTTP**, **reglas de negocio** y **acceso a datos**.

```
                    HTTP
                      │
        ┌─────────────▼──────────────┐
        │  app/api/routes/            │  Router: status codes, response_model,
        │  health.py, invoices.py      │  Depends. Cero lógica de negocio.
        └─────────────┬──────────────┘
                      │
        ┌─────────────▼──────────────┐
        │  app/services/invoice.py    │  Service: reglas de negocio.
        │                            │  Decide 404 vs 409, normaliza, transacciona.
        └─────────────┬──────────────┘
                      │
        ┌─────────────▼──────────────┐
        │  app/repositories/invoice.py│  Repository: TODO el SQL.
        └─────────────┬──────────────┘
                      │
        ┌─────────────▼──────────────┐
        │  app/models/invoice.py      │  Model: mapeo de tabla.
        └─────────────┬──────────────┘
                      │
                  PostgreSQL
```

En paralelo, dos capas transversales:

- **`app/schemas/`** — Pydantic. Valida la entrada y serializa la salida.
- **`app/core/`** — configuración (`Settings`), errores de dominio (`AppError`) y
  resolución del secreto de la base (`secrets.py`).

Y una pieza clave: **`app/main.py`** registra los handlers globales de error. Sin ellos,
cada fallo devolvería un `{"detail": ...}` con formato distinto según dónde explotó.
Con ellos, **toda** respuesta de error tiene la misma forma:

```json
{
  "error": {
    "code": "invoice_not_found",
    "message": "Invoice with id 42 was not found.",
    "details": null
  }
}
```

### Estructura de directorios

```
.
├── app/
│   ├── main.py                  # fábrica de la app, routers, handlers de error
│   ├── api/
│   │   ├── deps.py              # get_db, get_invoice_service
│   │   └── routes/              # health.py, invoices.py
│   ├── core/
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   └── errors.py            # AppError y sus subclases
│   ├── db/
│   │   ├── base.py              # Base declarativo
│   │   └── session.py           # engine, SessionLocal, get_db
│   ├── models/invoice.py        # tabla invoices
│   ├── schemas/invoice.py       # InvoiceCreate, InvoiceRead, InvoiceList
│   ├── repositories/invoice.py  # acceso a datos
│   └── services/invoice.py      # reglas de negocio
├── alembic/                     # migraciones
├── tests/
│   ├── conftest.py
│   ├── unit/                    # lógica del service, sin base de datos
│   └── integration/             # API completa contra PostgreSQL
├── infra/terraform/             # ECR + base ECS Fargate, con tests offline
│   ├── environments/            # un .tfvars por ambiente
│   └── tests/                   # terraform test con mock_provider
├── docker/postgres/init/        # script que crea la base de tests
├── docker-compose.yml
├── Dockerfile
├── .github/workflows/ci.yml
└── pyproject.toml
```

### Endpoints

| Método | Ruta | Respuesta | Errores |
|---|---|---|---|
| `GET` | `/health` | `200` `{"status":"ok","database":"ok"}` | `503` si la base no responde |
| `POST` | `/invoices` | `201` + header `Location` | `409` duplicado, `422` payload inválido |
| `GET` | `/invoices/{id}` | `200` | `404` |
| `GET` | `/invoices?limit=&offset=` | `200` `{items,total,limit,offset}` | `422` parámetros inválidos |

`limit` va de 1 a 100 (por defecto 20), `offset` de 0 en adelante.

---

## 3. Ejecutar localmente

Requisitos: Python 3.12 y [uv](https://docs.astral.sh/uv/). Docker solo hace falta para
la base de datos.

```bash
# 1. Dependencias (crea .venv con Python 3.12 e instala todo)
uv sync --extra dev

# 2. Variables de entorno
cp .env.example .env

# 3. Base de datos (PostgreSQL en el puerto 5433)
docker compose up -d postgres

# 4. Esquema
uv run alembic upgrade head

# 5. API
uv run uvicorn app.main:app --reload --port 8010
```

La API queda en <http://localhost:8010> y la documentación en
<http://localhost:8010/docs>.

> El puerto **8010** se usa tanto en local como en Docker Compose para que sea el
> mismo en todas partes. El 8000 es el que ocupa FastAPI por defecto y suele chocar
> con otras aplicaciones locales.

Para detener los servicios:

```bash
docker compose down
```

---

## 4. Ejecutar con Docker Compose

```bash
docker compose up --build
```

Levanta tres servicios:

| Servicio | Qué hace |
|---|---|
| `postgres` | PostgreSQL 16 con `pg_isready` como healthcheck. Puerto **5433** en el host. |
| `migrate` | Job de una sola ejecución: aplica `alembic upgrade head` y termina. |
| `api` | La API en Uvicorn. Puerto **8010** en el host. |

El orden está garantizado por `depends_on`: la API espera a que Postgres esté *healthy*
y a que `migrate` haya terminado con éxito.

```bash
curl http://localhost:8010/health
# {"status":"ok","database":"ok"}
```

Detener todo:

```bash
docker compose down -v     # -v borra también el volumen de datos
```

> `docker compose up` queda en primer plano: la API escribe los logs en la terminal.
> `Ctrl+C` para detenerlo, o `docker compose up --build -d` para correrlo en segundo
> plano.

---

## 5. Tests

```bash
uv run pytest                                   # toda la suite
uv run pytest tests/unit -v                     # solo unitarios
uv run pytest tests/integration -v              # solo de integración
uv run pytest --cov=app --cov-report=term-missing
```

> Los tests de integración necesitan PostgreSQL levantado
> (`docker compose up -d postgres`). Sin la base, la suite falla al intentar migrar
> el esquema de test. Los tests unitarios no dependen de ella.

La cobertura se mide solo sobre `app/`. El umbral está configurado en
`pyproject.toml` y **el comando falla si la cobertura baja del 80%**:

```toml
[tool.pytest.ini_options]
addopts = "--cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=80"
```

Estado actual: **39 tests, 100% de cobertura** sobre `app/`.

### Qué se testea y cómo

- **Unitarios** (`tests/unit/`) — el service con un repository en memoria. No tocan la
  base de datos: son rápidos y aíslan la lógica de negocio.
- **De integración** (`tests/integration/`) — la API completa contra **PostgreSQL real**.

Se usa PostgreSQL real y no SQLite a propósito: SQLite no reproduce fielmente
`Numeric`, `Enum` ni restricciones `UNIQUE`, así que un test verde en SQLite puede
fallar en PostgreSQL. Un test que miente es peor que no tener test.

La base de tests se crea sola (el script `docker/postgres/init/` la crea al inicializar
el contenedor) y **se migra con Alembic**, no con `create_all`. El esquema tiene una
única fuente de verdad.

El aislamiento entre tests se hace con una transacción externa: cada test corre dentro
de una transacción que se revierte al terminar, aunque el código del test haga
`commit`.

---

## 6. Swagger

Con la API levantada:

| URL | Qué es |
|---|---|
| <http://localhost:8010/docs> | Swagger UI interactivo |
| <http://localhost:8010/redoc> | ReDoc |
| <http://localhost:8010/openapi.json> | Esquema OpenAPI en JSON |

En local y en Docker Compose la API escucha en el mismo puerto.

---

## 7. Decisiones técnicas

| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| `Decimal` / `Numeric(12,2)` para el monto | `float` | `float` acumula error de redondeo. Es un bug que no aparece en el desarrollo y sí en la factura. |
| `invoice_number` **UNIQUE en la base** | Verificar duplicados solo en Python | La base es la única que puede garantizar unicidad ante concurrencia. Python verifica, la base garantiza. |
| Normalizar `invoice_number` con `strip()` + `upper()` | Case-sensitive | `"INV-1"` y `" inv-1 "` son la misma factura. Normalizar evita dos facturas que en realidad son una. |
| SQLAlchemy 2 **síncrono** + psycopg3 | Async | Menos boilerplate y más legible. El async se puede agregar después sin cambiar los contratos. |
| Alembic para el esquema | `create_all` al arrancar | Versionado real del esquema. `create_all` no permite evolucionar datos que ya existen. |
| PostgreSQL real en los tests | SQLite en memoria | SQLite no es fiel con `Numeric`, `Enum` ni `UNIQUE`. |
| `/health` hace `SELECT 1` y devuelve 503 si la base cae | Siempre 200 | Un health check que dice "ok" con la base caída es peor que no tener health check: el orquestador no reinicia nada. |
| Formato único de error | `{"detail": ...}` de FastAPI | Un cliente que parsea dos formatos distintos se rompe. |
| Multi-stage Docker, usuario no-root | Imagen simple con root | Un contenedor corriendo como root es el hallazgo más fácil de una revisión de seguridad. |
| Sin `uvicorn[standard]` en la imagen | Extra completo en runtime | `uvicorn[standard]` trae el watcher de `--reload` y el event loop acelerado: son comodidades de desarrollo, no de producción. |
| Servicio `migrate` como job aparte | Migrar en el entrypoint de la API | Distingue un job de una sola ejecución de un servicio de larga vida. Con N réplicas, migrar en el entrypoint corre la migración N veces. |
| **El secreto lo resuelve la plataforma, no la app** | Que la app sea cliente de Secrets Manager | La app no necesita SDK de AWS ni permisos de IAM: no sabe que existe un secret manager. El patrón alternativo (la app rota el secreto en caliente) se documenta en el README de infra. |
| **Migración como task de una sola ejecución** | Migrar en el entrypoint de la API | El entrypoint corre una migración por réplica; con un despliegue rolling son varias migraciones concurrentes. |
| **Tag de imagen explícito** (`image_tag`) | Fijar `latest` | El repo ECR es inmutable: un tag reusado sería rechazado por el registry. En un pipeline real es el SHA del commit. |
| `environment` sin default | `environment = "dev"` por defecto | Un `plan` sin `--var-file` apuntaría en silencio a dev. El error más caro no es de sintaxis: es desplegar el ambiente equivocado. |
| Sin prefijo `/v1` en las rutas | Versionado en el path | Mantiene el proyecto chico. Es una simplificación consciente, documentada como tal. |

### Detalles que conviene conocer

- **Pydantic v2 serializa `Decimal` como string** en JSON: `"1250.50"`, no `1250.50`.
  Es intencional (preserva precisión) y puede sorprender a un cliente.
- **`condecimal` ya devuelve un `Annotated`.** Envolverlo en otro
  `Annotated[Decimal, condecimal(...)]` hace que Pydantic **descarte todas las
  restricciones en silencio**, sin error ni warning. La forma correcta es:
  ```python
  Amount = condecimal(gt=0, max_digits=12, decimal_places=2)
  ```
- **El enum de SQLAlchemy guarda el nombre del miembro** (`ISSUED`), no el valor
  (`issued`). Con un `CHECK` sobre los valores, todo `INSERT` fallaba. Se corrige con
  `values_callable=lambda enum_cls: [member.value for member in enum_cls]`.

---

## 8. Qué es práctica real y qué es práctica personal

Esta sección es deliberadamente honesta, porque el valor de este repositorio está en
que se pueda defender cada línea.

### Es práctica personal (código escrito desde cero)

- Toda la aplicación: modelos, schemas, repository, service, routers, handlers.
- La suite de tests (39 tests) y la decisión de probar contra PostgreSQL real.
- El `Dockerfile` multi-stage, el `docker-compose.yml` y el script de inicialización.
- La normalización de `invoice_number`, el formato único de error, el contrato de
  `/health`.
- La estructura del proyecto y el orden de las capas.

### Es práctica de herramientas declarativas (configuración, no operación)

- **`infra/terraform/`** — la infraestructura **sí se aplicó**, pero **nunca contra
  una cuenta real de AWS**. Se aplicó contra [Floci](https://floci.io/aws/), un
  emulador local de AWS en Docker: **33 recursos** (VPC, subnets, NAT Gateway,
  security groups, ALB, target group, listener, ECR, ECS cluster, dos task
  definitions, un service, IAM, CloudWatch Logs, RDS y Secrets Manager). La task
  de migración corrió `alembic upgrade head` y salió con código 0; la task de la
  API levantó el container, recibió el secreto resuelto, se conectó al RDS y
  respondió `201`, `200`, `409` y `404`.
  Lo que **no** existe es una cuenta de AWS: no hay credenciales en este
  repositorio, `terraform plan` y `terraform apply` contra AWS real nunca se
  ejecutaron, y **no hay ningún recurso de AWS creado por este proyecto**. Lo que
  se demuestra es escribir y probar IaC, no haber operado producción.
- **`.github/workflows/ci.yml`** — el pipeline está escrito y sus comandos se
  ejecutaron localmente en cada etapa, pero su primera ejecución real ocurre en el
  primer push. Tampoco hay evidencia de haber mantenido un pipeline en producción.

### Lo que este repositorio NO es

- No es un proyecto de cliente ni una herramienta en uso.
- No hay usuarios reales, tráfico real ni datos reales.
- No hay experiencia laboral detrás de este código. Todo es práctica deliberada.
- No hay ningún recurso en AWS. La infraestructura se validó contra un emulador
  local, no contra la nube.

Lo que sí se puede defender: **las decisiones y sus porqués**. Que el repositorio sea
pequeño a propósito es una decisión, no una limitación.

---

## 9. Cómo funciona Terraform

Terraform declara infraestructura como código: se describe el estado deseado y la
herramienta calcula los cambios necesarios.

```bash
cd infra/terraform

terraform init -input=false     # descarga el provider; el backend local no toca AWS
terraform fmt -check -recursive  # verifica el formato
terraform validate              # valida la configuración sin tocar AWS
terraform test                  # tests del plan, offline y sin credenciales
```

Los cuatro comandos pasan en verde con el provider `hashicorp/aws` 6.70.0.

### Un archivo de variables por ambiente

Los valores de cada ambiente viven en `infra/terraform/environments/`:

```bash
terraform plan -var-file=environments/prod.tfvars
```

La variable `environment` **no tiene default a propósito**: si lo tuviera, un
`terraform plan` sin `--var-file` apuntaría en silencio a `dev`. Al ser
obligatoria, el comando falla y no hay forma de desplegar el ambiente
equivocado por olvido.

| Variable | Default | Sensitive |
|---|---|---|
| `environment` | **ninguno (obligatoria)** | no |
| `database_password` | **ninguno (obligatoria)** | **sí** |
| `image_tag` | `latest` | no |
| `aws_region` | `us-east-1` | no |
| `project_name` | `invoice-api-practice` | no |
| `container_cpu` / `container_memory` | `256` / `512` | no |
| `rds_instance_class` / `rds_allocated_storage` | `db.t4g.micro` / `20` | no |
| `tags` | `{}` | no |

La regla de los secretos: **los `.tfvars` versionados llevan valores que no son
secretos; los secretos llegan por variable de entorno**
(`TF_VAR_database_password`). Limitación conocida y citada en el README de
infra: Terraform guarda los valores de variables en el state file **en texto
plano**, aunque estén marcados como `sensitive`; por eso un proyecto real
crearía el secreto fuera de Terraform y solo referenciaría su ARN.

### Probar la infraestructura sin credenciales

`terraform test` corre los tests de `infra/terraform/tests/`. Usan
`mock_provider`, que reemplaza el provider de AWS por uno falso que **no hace
ninguna llamada a la API**: sin credenciales, sin cuenta y sin costo. Lo que se
verifica es el plan — que cada ambiente produzca los nombres correctos, que la
base no sea accesible desde internet y que **la contraseña no aparezca en la task
definition**.

### Practicar localmente con Floci

[Floci](https://floci.io/aws/) es un emulador de AWS libre que corre en Docker.
Implementa las APIs de AWS de verdad: el registry de ECR es un `registry:2` OCI
real, ECS lanza contenedores Docker reales y RDS corre un PostgreSQL real.

```bash
docker compose --profile aws-emulator up -d floci

export AWS_ENDPOINT_URL=http://localhost:4566 AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test
export TF_VAR_database_password="una-password-de-prueba"

cd infra/terraform
terraform init -reconfigure -backend-config="path=floci.tfstate"
terraform apply -auto-approve -var-file=environments/dev.tfvars -var image_tag=v1
```

Con esto se crean los 33 recursos, se pushea la imagen al ECR, corre la task de
migración y la API queda sirviendo contra el RDS emulado. El detalle completo
—incluidos los tres workarounds necesarios por bugs del emulador— está en
[`infra/terraform/README.md`](infra/terraform/README.md).

### Qué define esta configuración

| Capa | Recursos |
|---|---|
| **Red** | VPC, 2 subnets públicas, 2 privadas, Internet Gateway, NAT Gateway + EIP, 2 route tables, 3 security groups |
| **Entrada** | Application Load Balancer, target group con health check en `/health`, listener HTTP |
| **Cómputo** | ECS cluster, task definition de la API, task definition de migración, ECS service |
| **Datos** | RDS PostgreSQL (`db.t4g.micro`, no accesible desde internet) en un DB subnet group |
| **Secretos** | Secrets Manager con user, password, host, port y dbname de la base |
| **Imagen** | Repositorio ECR con tags inmutables y política de ciclo de vida |
| **Operación** | IAM role de ejecución (logs + ECR + Secrets Manager) y log group de CloudWatch |

### Cómo llega el secreto al contenedor

La contraseña **no viaja en la task definition**. El agente de ECS resuelve el
secreto de Secrets Manager y lo inyecta como variable de entorno:

```
Secrets Manager (JSON)
   → env var DATABASE_SECRET dentro del container
   → la app parsea el JSON y arma la URL de SQLAlchemy
```

La app **no conoce AWS**: no tiene SDK de AWS, no pide permisos de IAM, no sabe
que existe un secret manager. Solo lee una variable de entorno. La resolución
del secreto vive en `app/core/secrets.py`, en una función pura que se testea sin
mocks.

El detalle de diseño que más se pregunta en una entrevista: **Terraform guarda
los valores de las variables en el state file en texto plano**, aunque estén
marcadas como `sensitive`. Por eso un proyecto real crea el secreto **fuera** de
Terraform y referencia solo su ARN. Acá se construye desde una variable, que es
una simplificación documentada.

### El orden del despliegue

La API no arranca contra una base sin esquema. El orden correcto es:

1. `terraform apply` — crea la infraestructura y registra las task definitions.
2. Correr la **task de migración** y esperar a que salga con código 0.
3. Mover el **service** a la task definition nueva.

Migrar desde el entrypoint de la API sería un error: correría una migración por
réplica, y con un despliegue rolling eso son varias migraciones concurrentes.

### Practicar localmente con Floci

[Floci](https://floci.io/aws/) es un emulador de AWS libre que corre en Docker.
Implementa las APIs de AWS de verdad: el registry de ECR es un `registry:2` OCI
real, ECS lanza contenedores Docker reales y RDS corre un PostgreSQL real.

```bash
docker compose --profile aws-emulator up -d floci

export AWS_ENDPOINT_URL=http://localhost:4566 AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test
export TF_VAR_database_password="una-password-de-prueba"

cd infra/terraform
terraform init -reconfigure -backend-config="path=floci.tfstate"
terraform apply -auto-approve -var-file=environments/dev.tfvars -var image_tag=v1
```

Con esto se crean los 33 recursos, se pushea la imagen al ECR, corre la task de
migración y la API queda sirviendo contra el RDS emulado. El detalle completo
—incluidos los workarounds por bugs del emulador— está en
[`infra/terraform/README.md`](infra/terraform/README.md).

### Riesgo de costo

| Recurso | Costo |
|---|---|
| NAT Gateway | **~USD 32/mes** — el más caro de la configuración |
| ALB | **~USD 16/mes** |
| RDS `db.t4g.micro` | **~USD 15/mes** |
| Fargate (1 task 24/7) | ~USD 8.80/mes |
| ECR + logs | centavos |
| **Total estimado** | **~USD 72/mes** con el stack corriendo |

Apagar la base o el balanceador **no los elimina**: hay que borrarlos. El NAT
Gateway se puede reemplazar por VPC endpoints (ECR, S3, CloudWatch Logs), que
son gratis, y es el siguiente paso natural de esta configuración.

El detalle completo está en [`infra/terraform/README.md`](infra/terraform/README.md).

### Lo que deliberadamente NO incluye

- **VPC endpoints** para ECR, S3 y CloudWatch Logs. Son la alternativa gratuita
  al NAT Gateway y el siguiente paso natural de esta configuración.
- **Multi-AZ** en el RDS y en el service: una sola AZ, que es lo razonable para
  un ejercicio.
- **Certificados TLS** y un listener HTTPS: el ALB hoy escucha en HTTP.
- **WAF, autoscaling y alarms**: nada de eso se puede ejercitar sin tráfico real.
- **Backups automáticos** del RDS: el `skip_final_snapshot` es deliberado, la
  base es descartable porque el esquema se recrea con las migraciones.

### Backend remoto

El estado de Terraform se guarda en un bucket S3, con una tabla DynamoDB para
serializar los locks. **Este proyecto no crea ese bucket ni esa tabla.** El archivo
`backend.tf.example` tiene la configuración lista; para activarlo hay que crear el
bucket y la tabla a mano, **reemplazar** el bloque `backend "local"` de
`versions.tf` por el del ejemplo (Terraform solo admite un bloque `backend`) y
correr `terraform init`.

### Riesgo de costo

| Recurso | ¿Cuesta dinero? |
|---|---|
| ECR | Solo el almacenamiento: ~USD 0.10 por GB-mes. Una imagen ronda los 150–250 MB, o sea centavos. |
| CloudWatch Logs | Solo lo almacenado: ~USD 0.50 por GB ingerido. |
| Fargate | ~USD 0.012 por hora con 256 vCPU y 512 MiB (~USD 8.80/mes 24/7). **Una task que no corre no se cobra.** |
| VPC / NAT / ALB / RDS | No incluidos, justamente por su costo. |

El detalle completo está en [`infra/terraform/README.md`](infra/terraform/README.md).

---

## 10. Qué preguntas de entrevista permite practicar

Cada pregunta apunta a una decisión concreta de este repositorio.

**Diseño y arquitectura**
1. ¿Por qué separaste router, service y repository? ¿Qué pasa si no lo haces?
2. ¿Dónde va la validación: en el schema, en el service o en la base? ¿Por qué?
3. ¿Cómo garantizarías que el `invoice_number` sea único con diez peticiones simultáneas?
4. ¿Qué cambiarías si el dominio tuviera trescientos endpoints?

**Datos y transacciones**
5. ¿Por qué `Decimal` y no `float`? Mostrá el error con un ejemplo concreto.
6. ¿Qué es una transacción? ¿Qué pasa si el `commit` falla a mitad de camino?
7. ¿Cómo testearías una función que llama a un servicio externo?

**HTTP y errores**
8. ¿Cuál es la diferencia entre 400, 422 y 409? ¿Cuándo usas cada uno?
9. ¿Cómo garantizás que todos los errores de tu API tengan el mismo formato?
10. ¿Qué información de un error interno devolves al cliente y qué no? ¿Por qué?

**Testing**
11. ¿Por qué no SQLite en los tests? ¿Qué rompería?
12. ¿Cómo aislás los tests que tocan la base de datos?
13. ¿Qué es un test que miente? Dame un ejemplo.

**Operación**
14. ¿Cómo sabés si tu servicio está sano? ¿Qué pasa si la base se cae?
15. ¿Por qué el contenedor no corre como root?
16. ¿Cómo harías el despliegue? ¿Qué es un health check y para qué sirve?
17. ¿Qué pasa si el pipeline pasa pero la app está caída?

**Infraestructura**
18. ¿Qué es Terraform y qué problema resuelve?
19. ¿Por qué hay un NAT Gateway si los VPC endpoints son gratis? ¿Cuánto cuesta cada uno?
20. ¿Qué es un estado de Terraform y dónde debería vivir?
21. ¿Cómo evitás que alguien despliegue en `dev` cuando cree que va a `prod`?
22. ¿Dónde van los secretos en Terraform? ¿Qué pasa con el state file?
23. ¿Quién debería resolver el secreto: la plataforma o la app? ¿Cuándo cambia esa respuesta?
24. ¿Por qué la migración es una task aparte y no parte del arranque de la API?
25. ¿Qué pasa si el repositorio de imágenes es inmutable y despliegas siempre el mismo tag?
26. ¿Cómo testearías infraestructura sin gastar plata ni pedir credenciales?
27. ¿Qué es un emulador de AWS y en qué se diferencia de un mock?
28. ¿Por qué el ALB y el NAT Gateway son las fuentes de costo sorpresa? ¿Cómo los evitarías?

---

## 11. Pipeline de CI

`.github/workflows/ci.yml` corre en cada push y pull request a `main`, con cuatro jobs
independientes:

| Job | Qué verifica |
|---|---|
| `lint` | `ruff check` y `ruff format --check`. |
| `test` | PostgreSQL como servicio, `alembic upgrade head` y `pytest` con el gate de cobertura del 80%. |
| `docker` | Construye la imagen **y levanta el stack completo** para comprobar que la API responde. |
| `terraform` | `terraform fmt -check`, `init`, `validate`, `terraform test` (plan offline con provider simulado) y la validación de cada `environments/*.tfvars`. |

Los tres primeros comandos de Terraform no requieren credenciales: `validate`
solo necesita el *schema* del provider y `test` usa `mock_provider`, que no
hace ninguna llamada a la API.

---

## Licencia

MIT.
