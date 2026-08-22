# Arnés de medición

El proyecto declara dos números: **p95 por debajo de 200 ms** en la decisión de fraude
y **5.000 TPS** sostenidos en pico de quincena. Hasta ahora eran metas de diseño: el
dimensionamiento salía de la capacidad documentada de Bigtable, no de una corrida. Esto
es lo que los convierte en mediciones.

```bash
pip install httpx
python bench/loadtest.py --url https://<servicio>/score --rps 500 --seconds 120 --label base
python bench/loadtest.py --url https://<servicio>/score \
    --ramp 250,500,1000,2000,5000 --step-seconds 90 --label escalera
```

Cada corrida deja un JSON en `bench/resultados/` con la revisión de git, la
configuración y los percentiles. Sin eso, un número viejo no se puede atribuir a un
sistema concreto.

---

## Lo que hay que cerrar antes de que el número signifique algo

Cuatro huecos. El primero es el que decide si la cifra es real; los otros tres deciden
si es representativa.

| # | Hueco | Por qué invalida la medición | Cómo se cierra |
| --- | --- | --- | --- |
| 1 | `EnrichWithFraudScore` calcula el score con un MD5 del `transaction_id` | Medirías la latencia de un hash, no la de un modelo. Es **el** bloqueante | Desplegar el GBT tras un endpoint y llamarlo de verdad |
| 2 | El endpoint de Vertex está aprovisionado sin modelo desplegado | No hay nada que llamar | `deployed_model` + recursos dedicados o autoescalado en el Terraform |
| 3 | `min_instance_count = 0` en los servicios de Cloud Run | El primer request de cada instancia nueva paga arranque en frío y te ensucia el p99 | Súbelo a ≥1 para la corrida, y **dilo**: es una decisión de costo, no un truco |
| 4 | Dataflow sin `--max_num_workers` ni algoritmo de autoescalado | A 5.000 TPS el pipeline decide solo cuántos workers usa y la corrida no es reproducible | Fijar los flags y anotarlos en el artefacto |

**Sobre el punto 1, la decisión que te va a ahorrar el día:** un modelo de Spark MLlib
servido dentro de Spark arranca una JVM por petición y no cabe en 200 ms. Para servir,
reentrena el mismo GBT sobre las mismas features con XGBoost o LightGBM y súbelo a un
contenedor preconstruido de Vertex, o sírvelo desde Cloud Run. Es el mismo tipo de
modelo y la misma justificación —árboles por inferencia rápida y por importancia por
variable, que es lo que un regulador puede exigir— pero servible. Si cambias de
librería, **dilo en el informe**: "entrenado en Spark MLlib para el batch, servido con
un GBT equivalente para la ruta en línea" es una frase normal en producción.

---

## Qué mide este arnés, y qué no

**Mide** la ruta síncrona de decisión: sale la transacción, vuelve el veredicto. Ése es
el camino al que pertenece el SLA de 200 ms, porque es el único donde hay alguien
esperando. El pipeline de Beam es asíncrono: su latencia es de propagación, no de
decisión, y mezclarlas es el error que hace que un número de 200 ms no signifique nada.

**No mide** —y conviene que lo digas antes de que te lo pregunten— el retraso de
extremo a extremo hasta que el dato aterriza en BigQuery, ni el comportamiento con
datos reales en vez de sintéticos, ni un pico real de quincena con su distribución
horaria.

## Dos decisiones del generador de carga que sostienen el número

**Lazo abierto.** Un generador que espera la respuesta antes de mandar la siguiente
petición baja la carga justo cuando el servidor se degrada, y el percentil sale bonito
porque el propio experimento protegió al sistema. Éste manda a tasa fija pase lo que
pase.

**Latencia contra el instante previsto de envío, no contra el real.** Si el emisor se
atrasa porque su pool está saturado, esa espera la sufre el usuario igual. Descontarla
se llama *coordinated omission* y es la forma más común de publicar un p95 que no
existe. El artefacto trae las dos series: `latency_observed_ms` es la que se cita y
`latency_service_ms` la que aísla al servidor. **Que se separen es, por sí solo, la
señal de que el sistema entró en saturación**, y saber leer esa brecha vale más en una
entrevista que el número.

## Cómo se lee el resultado

- Cita **siempre** el percentil junto al número y la tasa a la que lo mediste:
  "p95 de X ms sosteniendo Y TPS durante Z minutos, 0 errores".
- Si la escalera se rompe antes de 5.000 TPS, ése también es un resultado y es mejor
  contarlo que esconderlo: "sostiene N TPS con p95 de X; por encima de eso el cuello es
  tal cosa". Un candidato que conoce su techo es más creíble que uno que dice no tenerlo.
- Guarda el artefacto. Cuando alguien pregunte "¿cómo lo mediste?", la respuesta es un
  archivo con la revisión de git dentro, no un recuerdo.
