# Lumina Bank - Arquitectura de Datos en Google Cloud Platform

## Visión General

Lumina Bank es una alianza público-privada que unifica el sistema financiero de **DataLandia**, integrando **12 instituciones bancarias independientes** con más de **9 millones de clientes** en un sistema financiero compartido, eficiente y en tiempo real.

Esta infraestructura como código (Terraform) implementa la arquitectura completa de datos en GCP, organizada en 4 fases:

```
┌─────────────────┐    ┌──────────────────┐    ┌───────────────────┐    ┌──────────────────┐
│   FASE 1        │    │   FASE 2         │    │   FASE 3          │    │   FASE 4         │
│   INGESTA       │───▶│   PROCESAMIENTO  │───▶│   ALMACENAMIENTO  │───▶│   SERVICIO       │
│                 │    │                  │    │                   │    │                  │
│ • Cloud Run     │    │ • Dataflow       │    │ • Pub/Sub Fan-Out │    │ • Cloud Run BFF  │
│ • Pub/Sub       │    │ • Dataproc       │    │ • BigQuery        │    │ • Cloud Run API  │
│ • Scheduler     │    │ • Memorystore    │    │ • Cloud Storage   │    │ • Vertex AI      │
│ • Cloud Func.   │    │ • Bigtable       │    │   (Data Lake)     │    │ • Looker Studio  │
│ • GCS Raw       │    │ • Vertex AI      │    │                   │    │                  │
└─────────────────┘    └──────────────────┘    └───────────────────┘    └──────────────────┘
```

---

## Puntos de Dolor Resueltos

### 1. Congestión de Procesamiento (Baja Latencia)
- **Cloud Memorystore (Redis):** Cache en memoria para consultas de transacciones recientes con latencia sub-milisegundo. Almacena el estado de las últimas transacciones por cliente, eliminando consultas repetidas a la base de datos durante picos de tráfico en días de pago.
- **Cloud Bigtable:** Base de datos NoSQL de baja latencia (~10ms) para perfiles de usuario y señales de fraude. Diseñada para millones de lecturas/escrituras por segundo, soporta los picos de cierres de mes sin degradación.
- **Cloud Dataflow (Streaming):** Procesamiento continuo y autoscalable que absorbe picos de demanda sin intervención manual. Los eventos de transacción se procesan en segundos, no en minutos.
- **Cloud Run (Autoescalado):** Los microservicios de ingesta escalan de 0 a 10 instancias automáticamente según la demanda.

### 2. Fragmentación de 12 Entidades Bancarias
- **Pub/Sub Fan-Out (12 suscripciones):** Un tópico de distribución con **12 suscripciones filtradas**, una por cada entidad bancaria. Cuando una transacción se aprueba, cada banco recibe únicamente las transacciones que le corresponden mediante filtros por atributo `bank_entity`. Esto permite:
  - Que cada banco procese sus transacciones a su propio ritmo
  - Retención de 31 días para reprocesamiento
  - Dead-letter topic para mensajes fallidos (máx. 5 intentos)
- **Procesamiento Centralizado:** Todas las transacciones de los 12 bancos fluyen por un pipeline único, permitiendo detección de **fraudes cruzados** (un usuario sospechoso en un banco es detectado en todos).
- **BigQuery como Data Warehouse Unificado:** Datasets con tablas particionadas y clusterizadas por `bank_entity`, permitiendo análisis inter-bancarios y reportes consolidados para el regulador.

### 3. Desajuste Demográfico e Infraestructura
- **Métricas por Sucursal/Cajero (`branch_volume_metrics`):** El procesamiento batch calcula la utilización de cada punto físico (cajeros, sucursales, corresponsales), identificando cuáles están subutilizados y cuáles congestionados.
- **Análisis Omnicanal:** La tabla de transacciones registra el canal (`APP`, `ATM`, `BRANCH`, `CORRESPONDENT`), permitiendo analizar patrones demográficos y optimizar la red física.

### 4. Analítica en Tiempo Real
- **KPIs en Streaming:** Métricas calculadas en ventanas de tiempo (TPS, latencia promedio, tasa de fraude, tasa de aprobación) escritas en BigQuery para consulta inmediata.
- **Productos de Datos Personalizados:** Tabla dedicada para recomendaciones de micro-créditos, seguros e inversiones generadas por el pipeline ML.
- **Pronóstico de Liquidez:** Modelo GBT entrenado diariamente con datos de 90 días, considerando días festivos y quincenas para predecir flujos de entrada/salida por banco.
- **Vertex AI Endpoints:** Modelos de fraude y liquidez desplegados como API para consumo en tiempo real.

---

## Estructura del Proyecto

```
terraform/
├── main.tf                          # Orquestación de módulos
├── variables.tf                     # Variables globales
├── outputs.tf                       # Outputs globales
├── provider.tf                      # Provider GCP y APIs
├── terraform.tfvars                 # Valores por defecto
├── modules/
│   ├── network/                     # VPC, subnets, firewall, IAM, service account
│   ├── ingestion/                   # Pub/Sub, Cloud Run, Cloud Function, Scheduler, GCS
│   ├── processing/                  # Dataflow, Dataproc, Redis, Bigtable, Vertex AI
│   ├── storage/                     # Pub/Sub fan-out, BigQuery, Data Lake
│   └── serving/                     # Cloud Run frontend/API, Vertex AI endpoints
└── scripts/
    ├── spark/
    │   ├── streaming_pipeline.py    # Pipeline Apache Beam (Dataflow)
    │   └── batch_processing.py      # PySpark batch (Dataproc)
    ├── cloud_function/              # Orquestador batch
    ├── cloud_run_ingestion/         # Microservicio de ingesta
    ├── cloud_run_api/               # API backend (BigQuery)
    ├── cloud_run_frontend/          # Frontend/BFF
    ├── dataflow/                    # Dockerfile para Dataflow Flex Template
    └── generate_test_data.py        # Generador de datos de prueba
```

---

## Prerequisitos

1. **Google Cloud SDK** instalado y configurado
2. **Terraform** >= 1.5.0
3. **Python** >= 3.12
4. Cuenta GCP con facturación habilitada (trial de 90 días)

## Inicialización Rápida

### Paso 1: Autenticación en GCP

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project project-413a2817-068f-425d-b1d
gcloud config set compute/region us-east1
```

### Paso 2: Inicializar Terraform

```bash
cd terraform/
terraform init
```

### Paso 3: Validar y planificar

```bash
terraform validate
terraform plan -out=plan.tfplan
```

### Paso 4: Aplicar la infraestructura

```bash
terraform apply plan.tfplan
```

> **Nota:** La primera ejecución puede tomar 10-15 minutos mientras se habilitan las APIs y se crean los recursos (especialmente Dataproc y Redis).

### Paso 5: Generar datos de prueba

```bash
# Generar CSV con 10,000 transacciones históricas (para batch)
python scripts/generate_test_data.py --mode batch --output ./test_data/ --count 10000

# Subir al bucket raw
gsutil cp ./test_data/transactions.csv gs://$(terraform output -raw raw_bucket_name)/historical/transactions/

# Enviar transacciones en streaming al endpoint de Cloud Run
python scripts/generate_test_data.py --mode streaming --url $(terraform output -raw cloud_run_ingestion_url) --count 100
```

### Paso 6: Subir scripts de Spark a GCS

```bash
gsutil cp scripts/spark/batch_processing.py \
  gs://$(gcloud config get-value project)-lumina-spark-scripts/scripts/
```

### Paso 7: Lanzar pipeline de Dataflow (streaming)

```bash
python scripts/spark/streaming_pipeline.py \
  --project=$(gcloud config get-value project) \
  --region=us-east1 \
  --input_subscription=$(terraform output -raw ingestion_pubsub_topic | sed 's/topics/subscriptions/')-dataflow-subscription \
  --output_table=$(gcloud config get-value project):lumina_streaming.transactions \
  --distribution_topic=$(terraform output -raw distribution_topic_id) \
  --runner=DataflowRunner \
  --temp_location=gs://$(gcloud config get-value project)-lumina-dataflow-temp/tmp \
  --staging_location=gs://$(gcloud config get-value project)-lumina-dataflow-staging/staging \
  --streaming
```

---

## Despliegue de Imágenes Docker (Cloud Run)

Para reemplazar las imágenes placeholder por las aplicaciones reales:

```bash
PROJECT_ID=$(gcloud config get-value project)
REGION=us-east1

# Construir y subir imagen de ingesta
cd scripts/cloud_run_ingestion/
gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/lumina-bank-images/ingestion-api:latest
gcloud run services update lumina-ingestion-api --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/lumina-bank-images/ingestion-api:latest --region ${REGION}

# Construir y subir imagen de API backend
cd ../cloud_run_api/
gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/lumina-bank-images/api-backend:latest
gcloud run services update lumina-api-backend --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/lumina-bank-images/api-backend:latest --region ${REGION}

# Construir y subir imagen de frontend
cd ../cloud_run_frontend/
gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/lumina-bank-images/frontend-bff:latest
gcloud run services update lumina-frontend-bff --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/lumina-bank-images/frontend-bff:latest --region ${REGION}
```

---

## Componentes por Módulo

### Módulo `network`
| Recurso | Propósito |
|---------|-----------|
| VPC + Subnet | Red privada con rangos secundarios para pods/services |
| Private IP Range + VPC Peering | Rango privado para servicios gestionados (Redis) vía Service Networking |
| VPC Connector | Permite a Cloud Run acceder a recursos en la VPC (Redis, Bigtable) — usa `ip_cidr_range 10.1.0.0/28` |
| Cloud NAT | Acceso a internet desde recursos privados |
| Firewall Rules | Tráfico interno + SSH para Dataproc |
| Service Account | Cuenta de servicio con roles amplios (trial mode) |
| IAM Default Compute SA | Roles de Cloud Build, Logging, Storage y Artifact Registry para Cloud Functions v2 |

### Módulo `ingestion`
| Recurso | Propósito |
|---------|-----------|
| Cloud Run (Ingesta) | Recibe transacciones HTTPS de 12 bancos, valida y encola |
| Pub/Sub Topic (Ingesta) | Cola principal de eventos transaccionales (retención 31d) |
| Pub/Sub DLT | Dead-letter topic para mensajes fallidos (máx 5 intentos) |
| Cloud Function | Orquestador batch: extrae de legacy, sube a GCS, lanza Dataproc |
| Cloud Scheduler | Cron diario a las 2 AM (America/Bogota) |
| GCS Raw/Landing | Bucket temporal para extracciones batch (lifecycle 90 días) |

### Módulo `processing`
| Recurso | Propósito |
|---------|-----------|
| Dataflow (config) | Buckets staging/temp para pipeline de streaming |
| Memorystore Redis | Cache sub-ms para transacciones recientes y estados de cliente |
| Bigtable | Perfiles de usuario y señales de fraude con latencia ~10ms |
| Dataproc | Clúster Spark (`e2-standard-2`, disco 50GB) para batch: tendencias, GBT, métricas de sucursal |
| Vertex AI Dataset | Dataset para entrenamiento de modelo de detección de fraude |

### Módulo `storage`
| Recurso | Propósito |
|---------|-----------|
| Pub/Sub Distribution | Tópico fan-out con 12 suscripciones filtradas por banco |
| BigQuery (Streaming) | Transacciones, KPIs, Reportes, Productos de Datos |
| BigQuery (Batch) | Pronóstico liquidez, tasas de interés, tipos de cambio, métricas |
| GCS Data Lake | Almacenamiento a largo plazo (Coldline después de 1 año) |

### Módulo `serving`
| Recurso | Propósito |
|---------|-----------|
| Cloud Run (Frontend) | Dashboard HTML + BFF que orquesta llamadas al API |
| Cloud Run (API) | API REST conectada a BigQuery, protegida con IAM |
| Artifact Registry | Repositorio Docker para imágenes de los servicios |
| Vertex AI Endpoints | Endpoints de fraude y liquidez para inferencia en tiempo real |

---

## Configuración para Looker Studio

Los datasets de BigQuery están preparados para ser conectados directamente a Looker Studio:

1. Ir a [Looker Studio](https://lookerstudio.google.com/)
2. Crear nuevo informe → Conectar a BigQuery
3. Seleccionar proyecto `project-413a2817-068f-425d-b1d`
4. Datasets disponibles:
   - `lumina_streaming.transactions` — Transacciones en tiempo real
   - `lumina_streaming.kpis_realtime` — KPIs por ventana de tiempo
   - `lumina_streaming.reports` — Reportes consolidados
   - `lumina_batch.liquidity_forecast` — Pronóstico de liquidez
   - `lumina_batch.branch_volume_metrics` — Métricas por sucursal
   - `lumina_batch.exchange_rates` — Tipos de cambio
   - `lumina_batch.interest_rates` — Tasas de interés

### Dashboards Sugeridos
- **Panel Ejecutivo:** TPS por banco, tasa de aprobación, monto total diario
- **Monitor de Fraude:** Score promedio por banco, transacciones bloqueadas, top clientes sospechosos
- **Liquidez:** Pronóstico de inflow/outflow por banco, comparativa con datos reales
- **Red Física:** Mapa de calor de utilización de sucursales/cajeros

---

## Limpieza

Para destruir toda la infraestructura:

```bash
terraform destroy
```

> **Advertencia:** Esto eliminará TODOS los recursos, incluyendo datos en BigQuery, Bigtable y Cloud Storage.

---

## Variables de Configuración

| Variable | Descripción | Default |
|----------|-------------|---------|
| `project_id` | ID del proyecto GCP | `project-413a2817-068f-425d-b1d` |
| `project_number` | Número del proyecto | `251068454544` |
| `region` | Región de despliegue | `us-east1` |
| `bank_entities` | Lista de 12 bancos | (ver variables.tf) |
| `pubsub_message_retention` | Retención Pub/Sub | `2678400s` (31 días) |
| `pubsub_max_delivery_attempts` | Intentos antes de DLT | `5` |
| `batch_schedule_cron` | Cron del batch | `0 2 * * *` (2 AM) |
| `dataproc_cluster_workers` | Workers Dataproc (mínimo 2) | `2` |
| `dataproc_machine_type` | Tipo de máquina Dataproc | `e2-standard-2` |
| `redis_memory_size_gb` | Memoria Redis | `1` GB |
| `bigtable_num_nodes` | Nodos Bigtable | `1` |

---

## Arquitectura de Seguridad

- **Service Account único** con roles amplios (configuración para trial GCP de 90 días)
- **VPC privada** con subredes dedicadas y acceso privado a Google APIs
- **Private Service Access** para conexión privada a servicios gestionados (Redis)
- **IAM para Default Compute SA:** Roles de Cloud Build, Logging, Storage y Artifact Registry necesarios para Cloud Functions v2
- **Cloud Run API Backend** protegido por IAM (solo invocable por el service account)
- **Cloud Run Frontend** público (accesible por usuarios finales)
- **Pub/Sub** con retención y dead-letter topics para garantizar entrega de mensajes
- **Cloud NAT** para acceso controlado a internet desde recursos privados
