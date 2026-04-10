**Rol:** Eres un Cloud Architect y Data Engineer Senior experto en Google Cloud Platform (GCP) e Infraestructura como Código (Terraform). 
**Objetivo:** Tu tarea es generar el código de infraestructura (Terraform) y los scripts base de configuración para implementar la arquitectura de datos de **Lumina Bank**, basándote en el contexto de negocio y el diagrama de arquitectura adjunto.

#### 1. Contexto de Negocio: Lumina Bank
Lumina Bank es una alianza público-privada creada para unificar el sistema financiero de la región de DataLandia. Actualmente, existen 12 instituciones bancarias independientes con más de 9 millones de clientes. La misión de Lumina Bank es crear un sistema financiero compartido único, eficiente, integrado y bajo demanda, aprovechando los activos combinados de estas 12 entidades metropolitanas, ofreciendo una experiencia omnicanal y decisiones en tiempo real.

#### 2. Puntos de Dolor a Resolver
La arquitectura debe estar diseñada para solucionar los siguientes problemas críticos del sistema actual:
1. **Congestión de Procesamiento:** Alta latencia en validación de transacciones y transferencias durante días de pago y cierres de mes.
2. **Fragmentación de Entidades:** 12 bancos compitiendo sin compartir información, lo que dificulta la prevención de fraudes cruzados y el perfilamiento de riesgo.
3. **Desajuste Demográfico y de Infraestructura:** Una red física (cajeros/oficinas) subutilizada, falta de integración entre la preferencia por atención humana de la tercera edad y los servicios 100% digitales de los jóvenes.
4. **Falta de analítica en tiempo real:** Incapacidad actual para ofrecer productos financieros personalizados, micro-créditos bajo demanda y rutas dinámicas de liquidez diaria.

#### 3. Especificaciones Técnicas de la Arquitectura GCP (Basado en el Diagrama)
Debes implementar la arquitectura dividida en 4 fases principales. Aquí tienes el detalle estricto de los componentes que debes aprovisionar:

**A. Fuentes de Datos (No requieren IaC, pero definen los flujos. Se va a necesitar imitar estos origenes usando los datos):**
*   **Streaming (Transaccional):** 12 entidades bancarias enviando datos desde Apps móviles, redes de cajeros y corresponsales bancarios.
*   **Batch (Histórico/Cierres):** Sistemas legacy con cierres bancarios (cuentas, saldos) y datos de mercado.

**B. Fase 1: Ingesta**
*   **Flujo Streaming:**
    *   **Cloud Run:** Un microservicio que recibe peticiones del usuario vía HTTPS, valida los datos y encola el evento.
    *   **Cloud Pub/Sub (Ingesta):** Tópico principal para recibir eventos transaccionales.
        *   *Configuración obligatoria:* Retención de mensajes de 31 días.
        *   *Configuración obligatoria:* Configurar un **Dead-letter topic** para capturar mensajes que fallan tras 5 intentos de entrega.
*   **Flujo Batch:**
    *   **Cloud Scheduler:** Configurado con un cronjob para gatillar el proceso batch diario.
    *   **Cloud Composer/Cloud Function (Apache Airflow):** Orquestador que se conecta a los sistemas legacy de los 12 bancos, extrae la información y la descomprime.
    *   **Cloud Storage (Raw/Landing):** Bucket para almacenar las extracciones procesadas temporalmente por Cloud Composer.

**C. Fase 2: Procesamiento**
*   **Flujo Streaming (Dataproc):**
    *   **Cloud Dataflow:** Procesamiento en streaming que:
        1. Lee los mensajes de Pub/Sub.
        2. Realiza limpieza y formato.
        3. Se integra con:
            *   **Cloud Memorystore (Redis):** Para cachéo rápido.
            *   **Cloud Bigtable:** Base de datos NoSQL de baja latencia para perfiles de usuario.
            *   **Vertex AI:** Para enviar/consultar features al Feature Store y **evaluar fraudes en tiempo real** (para recibir score si es o no fraude).
*   **Flujo Batch (Dataproc):**
    *   **Cloud Dataproc:** Clúster para procesamiento por lotes activado por un cloud scheduler diariamente a las 2 AM que lee desde Cloud Storage (transacciones históricas de los últimos 90 días) y:
        1. Calcula tendencias de movimientos, días festivos, etc.
        2. Entrena un modelo GBT (Gradient Boosted Trees) usando Spark ML.
        3. Procesa métricas de volumen de transacciones por cada sucursal/cajero.

**D. Fase 3: Almacenamiento**
*   **Capa de Mensajería de Salida (Pub/Sub - Fan-Out):**
    *   **Cloud Pub/Sub (Distribución):** Tópico con **12 suscripciones independientes** (una para cada entidad bancaria). Cuando el core del banco recibe el mensaje de transacción aprobada, actualiza la transferencia en su sistema interno. Si la rechaza, retiene los mensajes 31 días y también los mensajes que fallan tras 5 intentos.
*   **Data Warehouse (BigQuery):**
    *   *Dataset Streaming:* Tablas para Transacciones, KPIs, Reportes y Productos de Datos.
    *   *Dataset Batch:* Tablas para pronóstico de liquidez por entidad bancaria, tasa de interés por país y tipos de cambio.
*   **Data Lake (Cloud Storage):** Buckets para almacenamiento a largo plazo de sistemas históricos y datos de mercado.

**E. Fase 4: Servicio y Consumo**
*   **Cloud Run (Frontend/BFF):** Servicio de enrutado de peticiones que aloja el frontend y orquesta llamadas.  La respuesta de aprobada o bloqueada le llega al usuario a través de Cloud Run.
*   **Cloud Run (API Backend):** Microservicio que aloja la API de despliegue conectada a BigQuery, asegurada usando IAM (Identity and Access Management). Cloud Run lee la tabla de BigQuery responde con el pronóstico y datos.
*   **Looker Studio:** (Solo mención en el README, no requiere IaC de GCP directo, pero los datasets de BigQuery deben estar preparados para ser consultados por esta herramienta). De ser posible (y para sacarse buena nota, es importante implementar esto)
*   **Vertex AI (Endpoints):** Despliegue de los modelos entrenados (agentes de IA / modelos GBT) para ser consumidos por Cloud Run.

#### 4. Instrucciones de Salida para Claude Code:
1. **Estructura de Terraform:** Genera un proyecto estructurado en módulos (`ingestion`, `processing`, `storage`, `serving`, `network/security`).
2. **Código Listo para Producción:** Incluye variables (`variables.tf`), outputs (`outputs.tf`) y asignación de roles IAM necesarios entre servicios (ej. permisos de Cloud Run para publicar en Pub/Sub, permisos de Dataproc para leer GCS y escribir en BigQuery). En este caso, debido a que GCP esta en formato de 90 dias de prueba, usa los roles y permisos casi máximos, para facilitar la corrida de manera rápida (progress over perfection en esta parte).
3. **Documentación:** Genera un archivo `README.md` que explique exhaustivamente cómo inicializar esta infraestructura y cómo los componentes resuelven la baja latencia (uso de Memorystore/Bigtable) y la separación de 12 entidades (uso de fan-out en Pub/Sub).
4. **Simulación de Código Spark/Python:** Incluye un script base en Python (PySpark) de ejemplo para el Dataproc Streaming (leyendo de Pub/Sub y escribiendo en Bigtable/BigQuery) para darle una base a los ingenieros de datos.

**Variables importantes (aunque trata de no hardcodearlas)**

GCP_PROJECT_NUMBER=251068454544

GCP_PROJECT_ID=project-413a2817-068f-425d-b1d

GCP_PROJECT_NAME=LuminaBank
