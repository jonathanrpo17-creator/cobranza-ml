-- =====================================================================
-- 01_esquema.sql — Modelo relacional del proyecto de cobranza
--
-- Base: cobranza  |  Esquema: public  |  PostgreSQL 16+
-- Se puede ejecutar varias veces: borra y recrea las tablas (idempotente).
--
-- Grupos de tablas:
--   Datos de origen ......... deudores, creditos, perfil_solicitud
--   Desenlace (fuga) ........ resultados_recuperacion
--   Catálogos ............... segmentos, canales
--   Resultados del modelo ... predicciones
--   Simulación de campañas .. campanas, campana_asignaciones
-- =====================================================================

DROP VIEW  IF EXISTS vw_resumen_cohortes, vw_cartera_cobranza CASCADE;
DROP TABLE IF EXISTS campana_asignaciones, campanas, predicciones,
                     canales, segmentos, resultados_recuperacion,
                     perfil_solicitud, creditos, deudores CASCADE;

-- ---------------------------------------------------------------------
-- 1. DEUDORES: una fila por persona (MemberKey). Un deudor -> N créditos.
-- ---------------------------------------------------------------------
CREATE TABLE deudores (
    deudor_id                 INTEGER      PRIMARY KEY,
    member_key                VARCHAR(30)  NOT NULL UNIQUE,
    creditos_en_cobranza      SMALLINT     NOT NULL CHECK (creditos_en_cobranza >= 1),
    primera_originacion       DATE         NOT NULL
);
COMMENT ON TABLE deudores IS 'Deudores únicos de la población en cobranza. Datos seudonimizados (MemberKey).';

-- ---------------------------------------------------------------------
-- 2. CREDITOS: condiciones del crédito al originar + estado final.
-- ---------------------------------------------------------------------
CREATE TABLE creditos (
    credito_id                INTEGER      PRIMARY KEY,
    loan_key                  VARCHAR(30)  NOT NULL UNIQUE,
    listing_key               VARCHAR(30)  NOT NULL,
    deudor_id                 INTEGER      NOT NULL REFERENCES deudores(deudor_id),
    fecha_solicitud           TIMESTAMP,
    fecha_originacion         DATE         NOT NULL,
    trimestre_originacion     VARCHAR(10),
    plazo_meses               SMALLINT     NOT NULL CHECK (plazo_meses > 0),
    monto_original            NUMERIC(12,2) NOT NULL CHECK (monto_original > 0),
    cuota_mensual             NUMERIC(12,2),
    tasa_apr                  NUMERIC(7,5),
    tasa_interes              NUMERIC(7,5),
    rendimiento_inversionista NUMERIC(7,5),
    proposito_codigo          SMALLINT,
    porcentaje_financiado     NUMERIC(6,4),
    n_inversionistas          INTEGER,
    n_recomendaciones         SMALLINT,
    n_amigos_inversores       SMALLINT,
    monto_amigos              NUMERIC(12,2),
    calificacion_antigua      VARCHAR(5),   -- CreditGrade (antes de 2009)
    prosper_rating_num        SMALLINT,     -- ProsperRating (desde 2009)
    prosper_rating            VARCHAR(5),
    prosper_score             SMALLINT,
    rendimiento_estimado      NUMERIC(7,5),
    perdida_estimada          NUMERIC(7,5),
    retorno_estimado          NUMERIC(7,5),
    cuota_primer_default      SMALLINT,     -- LoanFirstDefaultedCycleNumber
    estado_credito            VARCHAR(30)  NOT NULL,  -- LoanStatus: NUNCA predictora
    fecha_cierre              DATE                    -- ClosedDate: NUNCA predictora
);
COMMENT ON COLUMN creditos.estado_credito IS 'Desenlace final (fuga). Solo para filtros y reportes.';
COMMENT ON COLUMN creditos.fecha_cierre   IS 'Fecha de castigo/cierre (fuga). Solo para madurez y partición temporal.';

-- ---------------------------------------------------------------------
-- 3. PERFIL_SOLICITUD: foto del deudor AL SOLICITAR (relación 1:1 con creditos).
--    Va separada de deudores porque cambia en cada solicitud (3FN).
-- ---------------------------------------------------------------------
CREATE TABLE perfil_solicitud (
    credito_id                       INTEGER PRIMARY KEY REFERENCES creditos(credito_id) ON DELETE CASCADE,
    fecha_consulta_bureau            TIMESTAMP,
    estado_residencia                VARCHAR(5),
    ocupacion                        VARCHAR(60),
    situacion_laboral                VARCHAR(30),
    meses_situacion_laboral          NUMERIC(6,1),
    propietario_vivienda             BOOLEAN,
    pertenece_grupo                  BOOLEAN,
    group_key                        VARCHAR(30),
    rango_ingresos                   VARCHAR(30),
    ingreso_verificable              BOOLEAN,
    ingreso_mensual                  NUMERIC(14,2),
    relacion_deuda_ingreso           NUMERIC(8,3),
    puntaje_bureau_min               SMALLINT,
    puntaje_bureau_max               SMALLINT,
    primera_linea_credito            DATE,
    lineas_credito_actuales          SMALLINT,
    lineas_credito_abiertas          SMALLINT,
    lineas_credito_7_anios           SMALLINT,
    cuentas_rotativas_abiertas       SMALLINT,
    pago_mensual_rotativo            NUMERIC(12,2),
    consultas_6_meses                SMALLINT,
    consultas_totales                SMALLINT,
    moras_actuales                   SMALLINT,
    monto_en_mora_al_solicitar       NUMERIC(14,2),
    moras_7_anios                    SMALLINT,
    registros_publicos_10_anios      SMALLINT,
    registros_publicos_12_meses      SMALLINT,
    saldo_rotativo                   NUMERIC(14,2),
    uso_tarjetas                     NUMERIC(6,3),
    cupo_disponible_tarjetas         NUMERIC(14,2),
    obligaciones_totales             SMALLINT,
    pct_obligaciones_sin_mora        NUMERIC(5,3),
    obligaciones_6_meses             SMALLINT,
    cambio_puntaje_desde_ultimo      SMALLINT,
    prosper_creditos_previos         SMALLINT,   -- nulo = sin créditos previos
    prosper_cuotas_facturadas        SMALLINT,
    prosper_cuotas_a_tiempo          SMALLINT,
    prosper_cuotas_atraso_menor_mes  SMALLINT,
    prosper_cuotas_atraso_mes_mas    SMALLINT,
    prosper_capital_prestado         NUMERIC(14,2),
    prosper_capital_pendiente        NUMERIC(14,2)
);

-- ---------------------------------------------------------------------
-- 4. RESULTADOS_RECUPERACION: desenlace y variables objetivo (1:1 con creditos).
--    Separada a propósito: contiene FUGA DE DATOS. El rol de solo lectura
--    de Power BI la ve, pero el modelo nunca la usa como entrada.
-- ---------------------------------------------------------------------
CREATE TABLE resultados_recuperacion (
    credito_id                      INTEGER PRIMARY KEY REFERENCES creditos(credito_id) ON DELETE CASCADE,
    lp_pagos_cliente                NUMERIC(14,2),
    lp_pagos_capital_cliente        NUMERIC(14,2),
    lp_intereses_cargos             NUMERIC(14,2),
    lp_comisiones_servicio          NUMERIC(14,2),
    lp_costos_cobranza              NUMERIC(14,2),
    lp_perdida_bruta_capital        NUMERIC(14,2),
    lp_perdida_neta_capital         NUMERIC(14,2),
    lp_recuperacion_no_capital      NUMERIC(14,2),
    exposicion_castigo              NUMERIC(14,2) NOT NULL,
    recuperacion_capital            NUMERIC(14,2) NOT NULL CHECK (recuperacion_capital >= 0),
    recuperacion_no_capital         NUMERIC(14,2) NOT NULL CHECK (recuperacion_no_capital >= 0),
    recuperacion_total              NUMERIC(14,2) NOT NULL CHECK (recuperacion_total >= 0),
    recuperacion_supera_exposicion  BOOLEAN       NOT NULL,
    objetivo_a                      SMALLINT      NOT NULL CHECK (objetivo_a IN (0, 1)),
    objetivo_b_tasa                 NUMERIC(7,6)  CHECK (objetivo_b_tasa BETWEEN 0 AND 1),
    objetivo_b_monto                NUMERIC(14,2) CHECK (objetivo_b_monto >= 0),
    meses_observacion               NUMERIC(6,1),
    exposicion_valida               BOOLEAN       NOT NULL,
    madura                          BOOLEAN       NOT NULL,
    en_modelado                     BOOLEAN       NOT NULL,
    conjunto                        VARCHAR(15)   CHECK (conjunto IN ('entrenamiento', 'validacion', 'inmadura', 'excluida'))
);
COMMENT ON TABLE resultados_recuperacion IS 'Desenlace observado y variables objetivo. Contiene fuga: NO usar como entrada del modelo.';

-- ---------------------------------------------------------------------
-- 5. CATÁLOGOS (se llenan en las Fases 7 y 8)
-- ---------------------------------------------------------------------
CREATE TABLE segmentos (
    segmento_id        SMALLINT     PRIMARY KEY,
    nombre             VARCHAR(60)  NOT NULL UNIQUE,
    descripcion        TEXT,
    accion_sugerida    VARCHAR(120),
    canal_sugerido     VARCHAR(30)
);

CREATE TABLE canales (
    canal_id                 SMALLINT     PRIMARY KEY,
    nombre                   VARCHAR(30)  NOT NULL UNIQUE,   -- WhatsApp, SMS, llamada, asesor
    costo_por_contacto_usd   NUMERIC(8,2) NOT NULL CHECK (costo_por_contacto_usd >= 0),
    efectividad_supuesta     NUMERIC(5,4) CHECK (efectividad_supuesta BETWEEN 0 AND 1),
    fuente_supuesto          TEXT         NOT NULL           -- todo canal es SIMULADO: se documenta
);

-- ---------------------------------------------------------------------
-- 6. PREDICCIONES: salida del modelo (Fases 6 y 7). Admite varias versiones.
-- ---------------------------------------------------------------------
CREATE TABLE predicciones (
    prediccion_id       BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    credito_id          INTEGER      NOT NULL REFERENCES creditos(credito_id) ON DELETE CASCADE,
    modelo_version      VARCHAR(40)  NOT NULL,
    es_vigente          BOOLEAN      NOT NULL DEFAULT FALSE,
    fecha_ejecucion     TIMESTAMP    NOT NULL DEFAULT NOW(),
    prob_recuperar      NUMERIC(7,6) NOT NULL CHECK (prob_recuperar BETWEEN 0 AND 1),
    tasa_esperada       NUMERIC(7,6) CHECK (tasa_esperada BETWEEN 0 AND 1),
    monto_esperado      NUMERIC(14,2),
    costo_gestion       NUMERIC(12,2),
    valor_esperado      NUMERIC(14,2),
    segmento_id         SMALLINT     REFERENCES segmentos(segmento_id),
    prioridad           INTEGER,
    UNIQUE (credito_id, modelo_version)
);

-- ---------------------------------------------------------------------
-- 7. SIMULACIÓN DE CAMPAÑAS (Fase 8)
-- ---------------------------------------------------------------------
CREATE TABLE campanas (
    campana_id          INTEGER      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre              VARCHAR(80)  NOT NULL,
    escenario           VARCHAR(20)  NOT NULL CHECK (escenario IN ('sin_modelo', 'con_modelo')),
    modelo_version      VARCHAR(40),
    presupuesto_usd     NUMERIC(14,2),
    supuestos           JSONB        NOT NULL,   -- costos, efectividades, capacidad: trazables
    fecha_simulacion    TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE TABLE campana_asignaciones (
    campana_id               INTEGER      NOT NULL REFERENCES campanas(campana_id) ON DELETE CASCADE,
    credito_id               INTEGER      NOT NULL REFERENCES creditos(credito_id) ON DELETE CASCADE,
    canal_id                 SMALLINT     REFERENCES canales(canal_id),
    contactado               BOOLEAN      NOT NULL,
    costo_usd                NUMERIC(10,2) NOT NULL DEFAULT 0,
    recuperacion_simulada    NUMERIC(14,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (campana_id, credito_id)
);
