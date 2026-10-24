# Terraform: de cero a producción

Guía para quien **nunca aplicó Terraform en un ambiente real**. No es un tutorial
de la sintaxis de HCL (eso está en la [documentación oficial](https://developer.hashicorp.com/terraform/tutorials))
ni del proyecto de este repositorio (eso está en el
[README de infra](../infra/terraform/README.md)). Es la explicación de **qué está
pasando realmente** cuando alguien corre `terraform apply`, porque hay cosas
que ningún tutorial te dice y que se aprenden a la mala.

---

## 1. El modelo mental

Lo primero que hay que desarmar es la palabra "crear". Terraform **no crea
recursos**: compara dos cosas y calcula los cambios.

```
   Lo que querés                    Lo que realmente existe
   (tu código .tf)                   (el state + la API de AWS)
          │                                    │
          └──────────────┬─────────────────────┘
                         ▼
                    terraform plan
              "qué habría que cambiar"
```

Ese "qué habría que cambiar" es una lista de acciones: crear, modificar,
destruir, o reemplazar. El `plan` **no toca nada**: es una simulación. El
`apply` es el que ejecuta la lista.

### El estado (state) es el corazón

Entre el código y la realidad hay un archivo (o una base de datos) con el mapa
de todos los recursos que Terraform administra y sus atributos actuales. Se
llama **state** y es el archivo más importante de todo el sistema.

Tres consecuencias que importan:

**1. El state es la fuente de verdad, no tu código.** Si el state dice que la
base tiene 20 GB y tu código dice 10, el plan propone 10. Si el state dice que
la base **no existe** (porque perdiste el state), el plan propone crearla, y
eso en una base real puede fallar o duplicar datos.

**2. El state es un archivo compartido.** Si dos personas aplican al mismo
tiempo contra el mismo state, se pisan. Por eso el backend remoto usa una
tabla de locks (DynamoDB) que serializa los applies.

**3. El state guarda valores sensibles en texto plano.** Marcar una variable
como `sensitive` lo esconde en la *salida*, pero el valor sigue escrito en el
state. Por eso en producción el state es un bucket S3 con acceso restringido y
versionado, y por eso los secretos de verdad (una contraseña de base) se
crean **fuera** de Terraform.

### El provider es el traductor

Terraform no habla con AWS: habla con el *provider*, que es un binario que
traduce las llamadas de Terraform a la API de cada nube (y a otros servicios:
Cloudflare, Kubernetes, GitHub...). El provider se descarga en el `init` y su
versión queda fijada en `.terraform.lock.hcl`, que **se commitea**.

Una consecuencia poco obvia: cambiar la versión del provider puede cambiar el
plan. Por eso el lock file se versiona y las upgrades de provider son un cambio
revisado como cualquier otro.

---

## 2. Cómo es de verdad en producción

Si en un tutorial hacés `terraform apply` con tus credenciales locales, en
producción casi nadie lo hace. El flujo real es así:

```
 1. Alguien abre un PR con cambios de .tf
 2. La CI corre: fmt, validate, plan
    → el plan se publica como artefacto o comentario del PR
 3. Alguien con permisos revisa y aprueba
 4. Un pipeline (o un rol de CI/CD) corre apply con credenciales temporales
 5. Terraform aplica, toma el lock, actualiza el state, suelta el lock
```

### Quién puede aplicar

Lo normal es que **nadie en el equipo aplique a mano**. El acceso al apply
está detrás de una aprobación. Un `apply` manual desde un laptop es la forma
más común de romper un ambiente de producción, porque:

- aplica con credenciales de una persona, no del pipeline;
- no deja rastro en el pipeline;
- puede aplicarse en el ambiente equivocado (y por eso el `environment` sin
  default en este proyecto).

### El state se protege como un asset

En producción el state vive en:

- **S3 con versioning activado**: si alguien lo corrompe, se recupera una
  versión anterior.
- **DynamoDB (o el lockfile de S3) para los locks**: dos applies simultáneos
  se serializan en vez de pisarse.
- **Acceso restringido**: quien puede leer el state puede leer los secretos
  que quedaron adentro.

### Un apply no es una transacción

Esto es lo que más sorprende. `terraform apply` ejecuta las acciones **de a
una**. Si la decimoquinta falla, las catorce anteriores **ya están aplicadas** y
el state ya las refleja. No hay rollback automático.

La estrategia habitual es que los cambios se hagan en pasos pequeños, para que
un fallo a mitad sea un problema conocido y no un incidente. Y por eso los cambios
que no se pueden deshacer (como borrar un bucket con datos) llevan
`prevent_destroy` o una protección explícita.

### Drift: la consola contra el código

Si alguien cambió un recurso desde la consola de AWS (un día hay que subir una
CPU a mano), la realidad se desvía del código. El próximo `plan` lo detecta y
propone **revertir el cambio**. Eso es **drift**, y hay dos filosofías:

- **Declarativa pura**: el código manda. El plan revierte lo que se hizo a mano.
  Es lo que hace Terraform por defecto.
- **Reconciliación**: se acepta el cambio a mano y se actualiza el código.

Lo importante es que **hay que elegir una y escribirla**, porque el
comportamiento por defecto (que el código mande) puede borrar, sin avisar, un
cambio que alguien hizo a propósito.

---

## 3. Conceptos que solo importan en producción

### Backend y state locking

El **backend** es dónde vive el state. Por defecto es local: un archivo
`terraform.tfstate` en el directorio. En producción es remoto (S3 + DynamoDB).

El backend se configura en un bloque `terraform {}` y se cambia con `init`.
Cuando cambia, Terraform pide migrar el state. Por eso este proyecto declara
el backend **explícitamente**:

```hcl
backend "local" {
  path = "terraform.tfstate"
}
```

Un backend implícito no se puede reconfigurar con `-backend-config`, y eso
impide practicing con un state separado del real (que es lo que hace el
emulador local en este proyecto).

### Workspaces

Un workspace es un estado adicional dentro del mismo backend. Se usan para
aislar ambientes (dev, staging, prod) o para trabajar en paralelo sobre la
misma configuración. El estado de cada workspace tiene su propio lock.

El detalle que muerde: **los workspaces no son un sustituto de separar
configuraciones**. Un error muy común es tener el mismo bucket de S3 para
`dev` y `prod` en dos workspaces distintos: cada uno tiene su state, cada uno
cree que el bucket no existe, y el segundo apply falla o lo destruye.

### Un state por ambiente

Este proyecto tiene dos ambientes que **conviven**: `development` (la base
local, sin Terraform) y `staging` (la infraestructura completa contra el
emulador). Cada uno tiene su propio archivo de state
(`floci.staging.tfstate`, `floci.dev.tfstate`), y por eso aplicar uno no
toca los recursos del otro.

El motivo es concreto y no es un detalle de estilo: **los nombres de los
recursos llevan el ambiente** (`invoice-api-practice-staging-db` vs
`invoice-api-practice-dev-db`). Terraform compara el código contra el state,
no contra lo que existe en la nube. Con un único state compartido, aplicar
`staging` propondría **destruir** todo lo de `development`, porque para
Terraform esos recursos sencillamente no existen.

En producción es el mismo concepto con otra mecánica: **una clave distinta en
el bucket S3 por ambiente** (`infra/staging/terraform.tfstate`,
`infra/prod/terraform.tfstate`), y a veces un bucket distinto.

Una consecuencia que conviene tener presente: con un state por ambiente, el
`plan` de cada uno se calcula **por separado**. No hay un comando que muestre
"todo lo que van a crear los tres ambientes" en un solo lugar.

### Módulos

Un módulo es un directorio de `.tf` reutilizable. Se consume con `source`:

```hcl
module "network" {
  source = "./modules/network"
  cidr   = "10.0.0.0/16"
}
```

Los módulos permiten reutilizar (una red, un bucket) y encapsular (el módulo
no expone todos sus internos). También agregan una capa de indirección que
complica el `plan`: un error puede estar en el módulo, en sus variables, o en
cómo se lo invoca.

Este proyecto **no usa módulos** a propósito: con un solo ambiente y una
sola configuración, un módulo de más es ruido. Es una decisión que se defiende
("cuando aparezca el segundo consumidor, ahí sí").

### Import

Traer un recurso que ya existe al state, para que Terraform lo administre sin
recrearlo:

```bash
terraform import aws_ecs_cluster.main arn:aws:ecs:us-east-1:1234:cluster/mi-cluster
```

Es la operación más infravalente y la que más cuesta al principio, porque el
import tiene efectos reales: si se importa el recurso equivocado, el siguiente
plan puede proponer destruirlo.

### `terraform state` y "state surgery"

Cuando el state se desincroniza de la realidad, hay herramientas para
arreglarlo sin recrear todo:

```bash
terraform state list          # ver qué hay en el state
terraform state rm <recurso> # sacarlo del state (el recurso queda en AWS, huérfano)
terraform state mv <de> <a>  # renombrarlo
```

Cada uno de esos comandos es una cirugía con consecuencias. Es el tipo de
operación que, en un equipo con permisos, hay que registrar.

### `-target`

Ejecuta solo una parte del plan. Es útil para debuggear un recurso
específico, pero es peligroso: deja el resto del state desactualizado, y el
próximo apply completo propone cambios que no esperabas.

Regla de equipo: `-target` solo en local, nunca en un pipeline.

---

## 4. Los errores clásicos

Estos son los que se ven en la práctica. Los que están en negrita **ocurrieron
o casi ocurren** en este proyecto.

### Perder el state

Si se borra el bucket de S3 que tenía el state, Terraform cree que **nada
existe**. El siguiente apply quiere recrear todo: la base, el cluster, el
balancer. En recursos con datos, eso puede fallar o, peor, crear un recurso
duplicado vacío mientras el original sigue ahí.

Defensa: versioning en el bucket, y nunca tocar el state a mano.

### El secreto en el state

Este proyecto lo documenta explícitamente en
[`secrets.tf`](../infra/terraform/secrets.tf): la contraseña se construye desde
una variable de Terraform, así que **queda en el state en texto plano**. En
producción, el secret se crea fuera de Terraform y el código solo referencia su
ARN.

### Recurso huérfano

Un recurso que existe en AWS pero no en el state. Terraform no lo ve, no lo
borra y no lo actualiza. Suele pasar cuando se crea algo a mano o cuando se
borra una entrada del state a ciegas.

La defensa es `import`, o borrar el recurso a mano.

**Repo ECR inmutable + `:latest`** — este proyecto lo tenía al principio: el
repositorio de imágenes era `IMMUTABLE` y la task definition apuntaba a
`:latest`. En el primer despliegue funciona; en el **segundo**, el registry
rechaza el tag repetido y el despliegue falla. La corrección fue una variable
`image_tag` explícita, que en un pipeline real es el SHA del commit.

**Migrar desde el entrypoint** — este proyecto lo tenía así al principio: la
API corría `alembic upgrade head` al arrancar. Con tres réplicas, eso son tres
migraciones concurrentes. La corrección fue una **task de migración** de una
sola ejecución, que se corre antes de mover el service.

### Apply a medio hacer

Un apply que falla en la mitad deja la infraestructura en un estado
intermedio. No hay rollback: se corrige con otro apply. Por eso los cambios
pequeños y los `prevent_destroy` importan más de lo que parece.

---

## 5. Qué ejercita este proyecto y qué no

Esta sección es la más importante de la guía, porque el valor de un portfolio
está en **saber qué se probó y qué no**.

### Sí se ejercitó, de verdad

| Concepto | Cómo se probó |
|---|---|
| El modelo de recursos y el plan | `terraform validate` y `terraform test` con `mock_provider`, sin credenciales. |
| Un apply real | Contra el emulador local Floci: **33 recursos** creados. |
| El backend remoto | S3 + DynamoDB reales en el emulador: el state terminó en el bucket, con la tabla de locks haciendo de lock. |
| Ambientes separados | Un `.tfvars` por ambiente y `environment` sin default. |
| La resolución de secretos | La task recibió el secreto inyectado por la plataforma y la app armó la URL. |
| El orden del despliegue | La task de migración corrió `alembic upgrade head` y salió con código 0, antes de levantar la API. |
| El costo real de la infraestructura | Calculado recurso por recurso. |

### No se ejercitó, y hay que decirlo

| Concepto | Por qué no |
|---|---|
| **Drift** | Requiere que alguien cambie un recurso fuera de Terraform. El emulador no lo modela. |
| **Permisos y aprobaciones** | No hay IAM de equipo ni pipeline de apply en este repo. |
| **El state compartido por un equipo** | El emulador lo usa de a uno. Los conflictos de lock no se pueden reproducir. |
| **Rollback** | `apply` no tiene rollback: se corrige con otro apply. |
| **Quotas y límites de AWS** | Un apply real puede fallar por límites de la cuenta, no por un error de configuración. |
| **Bugs de un provider nuevo** | Una upgrade de provider puede cambiar el plan. El lock file lo previene, no lo evita. |
| **El routing real de la VPC** | El emulador no implementa filtrado de security groups ni NAT de verdad. |
| **El proxy del ALB** | En el emulador no reenvía el tráfico. |

### La lección de fondo

Un `terraform apply` que funciona en el emulador **dice muy poco** sobre si va
a funcionar en una cuenta real. Lo que demuestra es que la **configuración es
correcta**: los recursos existen, los nombres son los que deben, las
dependencias están bien declaradas, el orden de despliegue es el correcto.

Lo que un apply real agrega es una capa de problemas que **no son de
Terraform**: permisos, cuotas, límites de la cuenta, el estado compartido, el
drift, y el hecho de que el state es un documento que hay que proteger.

Por eso alguien que dice "aplicué esto en producción" sin decir contra qué,
dice muy poco.

---

## 6. Si tuvieras que aplicar esto en un ambiente real

El orden, en serio:

1. Crear a mano el bucket de state (versionado) y la tabla de locks. El state
   tiene que existir **antes** del primer `init`, porque ese `init` lo necesita.
2. Configurar las credenciales con un rol, no con una persona. Lo más simple
   y lo más seguro: OIDC con el pipeline, para que no haya llaves largas
   dando vueltas.
3. Copiar `backend.tf.example` a `backend.tf`, reemplazar los `REPLACE_ME_*`, y
   correr `terraform init`.
4. Correr `terraform plan` **antes** de la primera aplicación y leerlo entero.
   Es la única vez que el plan es pequeño: después vas a ver cientos de líneas.
5. Aplicar por ambiente, empezando por `dev`, y **mirando el plan**.
6. A partir de ahí, todo apply pasa por el pipeline.

Y el primer `apply` real, hazlo con alguien que sepa AWS en la misma sala.

---

## Further reading

- [Documentación oficial de Terraform](https://developer.hashicorp.com/terraform/docs)
- [Terraform en AWS: los patrones que importan](https://docs.aws.amazon.com/prescriptive-guidance/terraform/latest/)
- [Best practices de Terraform](https://developer.hashicorp.com/terraform/cloud-docs/best-practices)
- El [README de `infra/terraform`](../infra/terraform/README.md) de este proyecto: la referencia operativa.
