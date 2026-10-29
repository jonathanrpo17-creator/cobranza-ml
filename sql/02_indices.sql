-- =====================================================================
-- 02_indices.sql — Índices para las consultas reales del proyecto
-- (las PRIMARY KEY y UNIQUE ya crean su propio índice automáticamente)
-- =====================================================================

-- Unir créditos con su deudor (vista y aplicación)
CREATE INDEX IF NOT EXISTS ix_creditos_deudor          ON creditos (deudor_id);
-- Partición temporal y filtros por fecha de cierre / cosecha
CREATE INDEX IF NOT EXISTS ix_creditos_fecha_cierre    ON creditos (fecha_cierre);
CREATE INDEX IF NOT EXISTS ix_creditos_originacion     ON creditos (fecha_originacion);
-- Filtros del dashboard por estado
CREATE INDEX IF NOT EXISTS ix_creditos_estado          ON creditos (estado_credito);
-- Selección de la población de modelado (índice parcial: solo las filas que importan)
CREATE INDEX IF NOT EXISTS ix_resultados_modelado      ON resultados_recuperacion (conjunto)
    WHERE en_modelado;
-- Predicción vigente de un crédito (aplicación) y ranking de priorización
CREATE INDEX IF NOT EXISTS ix_pred_vigente             ON predicciones (credito_id)
    WHERE es_vigente;
CREATE INDEX IF NOT EXISTS ix_pred_ranking             ON predicciones (modelo_version, valor_esperado DESC);
CREATE INDEX IF NOT EXISTS ix_pred_segmento            ON predicciones (segmento_id);
-- Resultados de una campaña por canal
CREATE INDEX IF NOT EXISTS ix_asignaciones_canal       ON campana_asignaciones (campana_id, canal_id);
