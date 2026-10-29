-- =====================================================================
-- 03_vistas.sql — Vistas de consumo para Power BI y la aplicación
-- Power BI se conecta a las VISTAS, no a las tablas: si el esquema cambia,
-- se ajusta la vista y el dashboard no se rompe.
-- =====================================================================

-- Una fila por crédito en cobranza, con todo lo que el dashboard necesita.
-- Las columnas de predicción quedan vacías hasta las Fases 6-7.
CREATE OR REPLACE VIEW vw_cartera_cobranza AS
SELECT
    c.credito_id,
    c.loan_key,
    d.deudor_id,
    d.creditos_en_cobranza,
    c.fecha_originacion,
    EXTRACT(YEAR FROM c.fecha_originacion)::INT          AS anio_originacion,
    c.fecha_cierre,
    EXTRACT(YEAR FROM c.fecha_cierre)::INT               AS anio_cierre,
    c.estado_credito,
    c.plazo_meses,
    c.monto_original,
    c.tasa_interes,
    COALESCE(c.prosper_rating, c.calificacion_antigua)   AS calificacion,
    c.cuota_primer_default,
    p.estado_residencia,
    p.situacion_laboral,
    p.rango_ingresos,
    p.ingreso_mensual,
    p.propietario_vivienda,
    p.puntaje_bureau_min,
    r.exposicion_castigo,
    r.recuperacion_total,
    r.objetivo_a                                          AS recupero_algo,
    r.objetivo_b_tasa                                     AS tasa_recuperacion,
    r.lp_costos_cobranza,
    r.meses_observacion,
    r.madura,
    r.en_modelado,
    r.conjunto,
    pr.modelo_version,
    pr.prob_recuperar,
    pr.tasa_esperada,
    pr.monto_esperado,
    pr.costo_gestion,
    pr.valor_esperado,
    pr.prioridad,
    s.nombre                                              AS segmento,
    s.accion_sugerida,
    s.canal_sugerido
FROM creditos c
JOIN deudores d                     ON d.deudor_id  = c.deudor_id
JOIN perfil_solicitud p             ON p.credito_id = c.credito_id
JOIN resultados_recuperacion r      ON r.credito_id = c.credito_id
LEFT JOIN predicciones pr           ON pr.credito_id = c.credito_id AND pr.es_vigente
LEFT JOIN segmentos s               ON s.segmento_id = pr.segmento_id;

-- Resumen por año de cierre y estado (página de resumen ejecutivo).
CREATE OR REPLACE VIEW vw_resumen_cohortes AS
SELECT
    EXTRACT(YEAR FROM c.fecha_cierre)::INT                         AS anio_cierre,
    c.estado_credito,
    COUNT(*)                                                       AS creditos,
    SUM(r.exposicion_castigo)                                      AS exposicion_usd,
    SUM(r.recuperacion_total)                                      AS recuperado_usd,
    ROUND(100.0 * AVG(r.objetivo_a), 2)                            AS pct_recupera_algo,
    ROUND(100.0 * SUM(r.recuperacion_total)
          / NULLIF(SUM(GREATEST(r.exposicion_castigo, 0)), 0), 2)  AS tasa_recuperacion_pct,
    SUM(CASE WHEN r.madura THEN 1 ELSE 0 END)                      AS creditos_maduros
FROM creditos c
JOIN resultados_recuperacion r ON r.credito_id = c.credito_id
GROUP BY 1, 2;
