# Lumina Bank — Queries para Demo

Project: `lumina-bank-big-data-2026`
Dataset: `lumina_streaming`
Tabla: `transactions`

---

## 1. Insertar data de demo (~600 filas)

```sql
INSERT INTO `lumina-bank-big-data-2026.lumina_streaming.transactions`
(transaction_id, bank_entity, customer_id, transaction_type, amount, currency,
 source_account, destination_account, destination_bank, channel, status,
 fraud_score, latitude, longitude, device_id,
 transaction_timestamp, processing_timestamp, metadata)
SELECT
  CONCAT('TX-', FORMAT_DATE('%Y%m%d', CURRENT_DATE()), '-', LPAD(CAST(n AS STRING), 6, '0')) AS transaction_id,
  ['banco-central-datalandia','banco-este-comercial','banco-federal-integrado',
   'banco-herencia-nacional','banco-innovacion-fintech','banco-mercantil-datalandia',
   'banco-norte-metropolitano','banco-oeste-industrial','banco-progreso-digital',
   'banco-solidario-regional','banco-sur-cooperativo','banco-union-popular'
  ][OFFSET(MOD(n, 12))] AS bank_entity,
  CONCAT('CUST-', LPAD(CAST(MOD(n*7, 5000) AS STRING), 5, '0')) AS customer_id,
  ['TRANSFER','PAYMENT','WITHDRAWAL','DEPOSIT'][OFFSET(MOD(n, 4))] AS transaction_type,
  CAST(ROUND(RAND() * 9500 + 50, 2) AS NUMERIC) AS amount,
  ['PEN','USD','EUR'][OFFSET(MOD(n, 3))] AS currency,
  CONCAT('ACC-', LPAD(CAST(MOD(n*13, 9999) AS STRING), 8, '0')) AS source_account,
  CONCAT('ACC-', LPAD(CAST(MOD(n*17, 9999) AS STRING), 8, '0')) AS destination_account,
  ['banco-central-datalandia','banco-este-comercial','banco-federal-integrado',
   'banco-herencia-nacional','banco-innovacion-fintech','banco-mercantil-datalandia'
  ][OFFSET(MOD(n, 6))] AS destination_bank,
  ['APP','APP','APP','ATM','BRANCH','CORRESPONDENT'][OFFSET(MOD(n, 6))] AS channel,
  -- Distribución realista: ~70% APPROVED, 15% REJECTED, 10% PENDING, 5% BLOCKED
  CASE
    WHEN MOD(n, 20) < 14 THEN 'APPROVED'
    WHEN MOD(n, 20) < 17 THEN 'REJECTED'
    WHEN MOD(n, 20) < 19 THEN 'PENDING'
    ELSE 'BLOCKED'
  END AS status,
  ROUND(RAND(), 4) AS fraud_score,
  ROUND(-12.0464 + (RAND() - 0.5) * 0.5, 6) AS latitude,
  ROUND(-77.0428 + (RAND() - 0.5) * 0.5, 6) AS longitude,
  CONCAT('DEV-', LPAD(CAST(MOD(n*23, 99999) AS STRING), 8, '0')) AS device_id,
  TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL CAST(RAND() * 43200 AS INT64) SECOND) AS transaction_timestamp,
  CURRENT_TIMESTAMP() AS processing_timestamp,
  TO_JSON(STRUCT(
    CONCAT('session-', CAST(MOD(n*31, 99999) AS STRING)) AS session_id,
    ['ios','android','web'][OFFSET(MOD(n, 3))] AS platform,
    ['Lima','Arequipa','Cusco','Trujillo','Piura'][OFFSET(MOD(n, 5))] AS city
  )) AS metadata
FROM UNNEST(GENERATE_ARRAY(1, 600)) AS n;
```

> Para más volumen, sube el `600` a `5000` en el `GENERATE_ARRAY`.

---

## 2. Verificación: transacciones por entidad y estado

```sql
SELECT bank_entity, status, COUNT(*) as total
FROM `lumina-bank-big-data-2026.lumina_streaming.transactions`
WHERE DATE(transaction_timestamp) = CURRENT_DATE()
GROUP BY bank_entity, status
ORDER BY total DESC;
```

---

## 3. Top entidades por volumen monetario

```sql
SELECT bank_entity, SUM(amount) AS volumen_total, COUNT(*) AS num_tx
FROM `lumina-bank-big-data-2026.lumina_streaming.transactions`
WHERE DATE(transaction_timestamp) = CURRENT_DATE()
GROUP BY bank_entity
ORDER BY volumen_total DESC;
```

---

## 4. Detección de fraude (score > 0.8)

```sql
SELECT bank_entity, channel, COUNT(*) AS sospechosas, AVG(fraud_score) AS score_promedio
FROM `lumina-bank-big-data-2026.lumina_streaming.transactions`
WHERE fraud_score > 0.8 AND DATE(transaction_timestamp) = CURRENT_DATE()
GROUP BY bank_entity, channel
ORDER BY sospechosas DESC;
```

---

## 5. Distribución por canal

```sql
SELECT channel, status, COUNT(*) AS total, ROUND(AVG(amount), 2) AS ticket_promedio
FROM `lumina-bank-big-data-2026.lumina_streaming.transactions`
WHERE DATE(transaction_timestamp) = CURRENT_DATE()
GROUP BY channel, status
ORDER BY channel, total DESC;
```
