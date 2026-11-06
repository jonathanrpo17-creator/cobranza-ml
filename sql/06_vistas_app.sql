-- =====================================================================
-- 06_vistas_app.sql — Vistas para la aplicación de consulta y Power BI (Fase 9)
-- Lo ejecuta el notebook 09. Si se vuelve a ejecutar el notebook 04, hay que
-- volver a ejecutar el 09 (el 04 recrea las tablas y borra estas vistas).
-- =====================================================================

-- Entradas del modelo: SIN desenlace (LP_*, estado, fecha de cierre) y SIN
-- identificadores de persona (member_key, group_key). Es lo mínimo para que la
-- aplicación recalcule la predicción y la explique con SHAP.
CREATE OR REPLACE VIEW vw_entradas_modelo AS
SELECT c.credito_id, c.loan_key, r.conjunto,
       c.fecha_originacion, c.plazo_meses, c.monto_original, c.cuota_mensual, c.tasa_interes,
       c.porcentaje_financiado, c.n_inversionistas, c.n_recomendaciones, c.n_amigos_inversores,
       c.proposito_codigo, c.prosper_rating, c.calificacion_antigua, c.cuota_primer_default,
       p.estado_residencia, p.ocupacion, p.situacion_laboral, p.meses_situacion_laboral,
       p.propietario_vivienda, p.pertenece_grupo, p.rango_ingresos, p.ingreso_verificable,
       p.ingreso_mensual, p.relacion_deuda_ingreso, p.puntaje_bureau_min, p.puntaje_bureau_max,
       p.primera_linea_credito, p.lineas_credito_actuales, p.lineas_credito_abiertas,
       p.lineas_credito_7_anios, p.cuentas_rotativas_abiertas, p.pago_mensual_rotativo,
       p.consultas_6_meses, p.consultas_totales, p.moras_actuales, p.monto_en_mora_al_solicitar,
       p.moras_7_anios, p.registros_publicos_10_anios, p.registros_publicos_12_meses,
       p.saldo_rotativo, p.uso_tarjetas, p.cupo_disponible_tarjetas, p.obligaciones_totales,
       p.pct_obligaciones_sin_mora, p.obligaciones_6_meses, p.cambio_puntaje_desde_ultimo,
       p.prosper_creditos_previos, p.prosper_cuotas_facturadas, p.prosper_cuotas_a_tiempo,
       p.prosper_cuotas_atraso_menor_mes, p.prosper_cuotas_atraso_mes_mas,
       p.prosper_capital_prestado, p.prosper_capital_pendiente
FROM creditos c
JOIN perfil_solicitud p        ON p.credito_id = c.credito_id
JOIN resultados_recuperacion r ON r.credito_id = c.credito_id
WHERE r.conjunto <> 'excluida';

-- Resultado de cada campaña simulada (página de ROI del dashboard)
CREATE OR REPLACE VIEW vw_roi_campanas AS
SELECT ca.campana_id, ca.nombre, ca.escenario, ca.presupuesto_usd,
       COUNT(*) FILTER (WHERE a.contactado)  AS creditos_gestionados,
       SUM(a.costo_usd)                      AS costo_usd,
       SUM(a.recuperacion_simulada)          AS recuperado_simulado_usd
FROM campanas ca
JOIN campana_asignaciones a ON a.campana_id = ca.campana_id
GROUP BY ca.campana_id, ca.nombre, ca.escenario, ca.presupuesto_usd;

-- Resultado por segmento y canal dentro de cada campaña
CREATE OR REPLACE VIEW vw_roi_segmentos AS
SELECT ca.nombre AS campana, ca.escenario, s.nombre AS segmento, cn.nombre AS canal,
       COUNT(*) FILTER (WHERE a.contactado)  AS creditos_gestionados,
       SUM(a.costo_usd)                      AS costo_usd,
       SUM(a.recuperacion_simulada)          AS recuperado_simulado_usd
FROM campana_asignaciones a
JOIN campanas ca        ON ca.campana_id = a.campana_id
JOIN predicciones pr    ON pr.credito_id = a.credito_id AND pr.es_vigente
JOIN segmentos s        ON s.segmento_id = pr.segmento_id
LEFT JOIN canales cn    ON cn.canal_id   = a.canal_id
GROUP BY ca.nombre, ca.escenario, s.nombre, cn.nombre;

GRANT SELECT ON vw_entradas_modelo, vw_roi_campanas, vw_roi_segmentos TO lector_bi;
