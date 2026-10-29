-- =====================================================================
-- 05_consultas_ejemplo.sql — Consultas de negocio sobre el modelo relacional
-- Se pueden ejecutar en pgAdmin (Query Tool) o desde el notebook 04.
-- =====================================================================

-- Q1. Línea base: ¿cuánto se recupera hoy sin modelo?
SELECT COUNT(*)                                             AS creditos,
       SUM(exposicion_castigo)                              AS exposicion_usd,
       SUM(recuperacion_total)                              AS recuperado_usd,
       ROUND(100.0 * AVG(objetivo_a), 2)                    AS pct_recupera_algo,
       ROUND(100.0 * SUM(recuperacion_total)
             / SUM(GREATEST(exposicion_castigo, 0)), 2)     AS tasa_recuperacion_pct
FROM resultados_recuperacion;

-- Q2. Tamaño de cada conjunto (partición temporal y cartera inmadura)
SELECT conjunto, COUNT(*) AS creditos, ROUND(100.0 * AVG(objetivo_a), 1) AS pct_recupera
FROM resultados_recuperacion
GROUP BY conjunto
ORDER BY conjunto;

-- Q3. Deudores con más de un crédito en cobranza (justifica la tabla deudores)
SELECT creditos_en_cobranza, COUNT(*) AS deudores
FROM deudores
GROUP BY creditos_en_cobranza
ORDER BY creditos_en_cobranza;

-- Q4. Recuperación por calificación, solo créditos maduros
SELECT calificacion,
       COUNT(*)                                   AS creditos,
       ROUND(100.0 * AVG(recupero_algo), 1)       AS pct_recupera,
       ROUND(100.0 * SUM(recuperacion_total)
             / SUM(GREATEST(exposicion_castigo, 0)), 1) AS tasa_cartera_pct
FROM vw_cartera_cobranza
WHERE en_modelado
GROUP BY calificacion
HAVING COUNT(*) >= 30
ORDER BY calificacion;

-- Q5. Recuperación según la cuota en que cayó en default (comportamiento de pago)
SELECT CASE WHEN cuota_primer_default IS NULL THEN 'sin dato'
            WHEN cuota_primer_default < 6     THEN '01: cuota 0-5'
            WHEN cuota_primer_default < 12    THEN '02: cuota 6-11'
            WHEN cuota_primer_default < 24    THEN '03: cuota 12-23'
            ELSE                                   '04: cuota 24+' END AS tramo_default,
       COUNT(*)                              AS creditos,
       ROUND(100.0 * AVG(recupero_algo), 1)  AS pct_recupera
FROM vw_cartera_cobranza
WHERE en_modelado
GROUP BY 1
ORDER BY 1;

-- Q6. Cosechas: resumen por año de cierre (vista para Power BI)
SELECT * FROM vw_resumen_cohortes ORDER BY anio_cierre, estado_credito;
