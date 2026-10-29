"""
Ingeniería de variables sin fuga de datos (Fase 5).

Regla de oro: el modelo se usa cuando el crédito ENTRA A COBRANZA. Toda variable
debe poder calcularse con información disponible en ese momento:
  - condiciones del crédito al originar (tabla creditos)
  - foto del deudor al solicitar (tabla perfil_solicitud)
  - comportamiento de pago hasta el default (cuota_primer_default)

Nada de resultados_recuperacion, estado_credito, fecha_cierre ni identificadores.

Este módulo lo usan el notebook 05 (entrenamiento) y la aplicación (Fase 9),
así que un crédito nuevo se transforma EXACTAMENTE igual que los de entrenamiento.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

# --------------------------------------------------------------------------
# Lista negra: columnas que NUNCA pueden ser variables del modelo
# --------------------------------------------------------------------------
COLUMNAS_PROHIBIDAS = {
    # identificadores
    "credito_id", "loan_key", "listing_key", "deudor_id", "member_key", "group_key",
    # desenlace (fuga)
    "estado_credito", "fecha_cierre", "creditos_en_cobranza",
    "lp_pagos_cliente", "lp_pagos_capital_cliente", "lp_intereses_cargos",
    "lp_comisiones_servicio", "lp_costos_cobranza", "lp_perdida_bruta_capital",
    "lp_perdida_neta_capital", "lp_recuperacion_no_capital",
    "exposicion_castigo", "recuperacion_capital", "recuperacion_no_capital",
    "recuperacion_total", "recuperacion_supera_exposicion",
    "objetivo_a", "objetivo_b_tasa", "objetivo_b_monto",
    "meses_observacion", "exposicion_valida", "madura", "en_modelado", "conjunto",
}

# Escala común para las calificaciones de las dos épocas (mismas letras)
ESCALA_CALIFICACION = {"AA": 7, "A": 6, "B": 5, "C": 4, "D": 3, "E": 2, "HR": 1}

# Situación laboral: las dos épocas de Prosper usan etiquetas distintas
UNIFICAR_SITUACION_LABORAL = {
    "Full-time": "Empleado", "Employed": "Empleado", "Part-time": "Empleado",
    "Self-employed": "Independiente",
    "Not employed": "Desempleado",
    "Retired": "Pensionado",
    "Other": "Otro",
    "Not available": "Sin dato",
}

CONSULTA_BASE = """
SELECT c.*,
       p.fecha_consulta_bureau, p.estado_residencia, p.ocupacion, p.situacion_laboral,
       p.meses_situacion_laboral, p.propietario_vivienda, p.pertenece_grupo,
       p.rango_ingresos, p.ingreso_verificable, p.ingreso_mensual, p.relacion_deuda_ingreso,
       p.puntaje_bureau_min, p.puntaje_bureau_max, p.primera_linea_credito,
       p.lineas_credito_actuales, p.lineas_credito_abiertas, p.lineas_credito_7_anios,
       p.cuentas_rotativas_abiertas, p.pago_mensual_rotativo, p.consultas_6_meses,
       p.consultas_totales, p.moras_actuales, p.monto_en_mora_al_solicitar, p.moras_7_anios,
       p.registros_publicos_10_anios, p.registros_publicos_12_meses, p.saldo_rotativo,
       p.uso_tarjetas, p.cupo_disponible_tarjetas, p.obligaciones_totales,
       p.pct_obligaciones_sin_mora, p.obligaciones_6_meses, p.cambio_puntaje_desde_ultimo,
       p.prosper_creditos_previos, p.prosper_cuotas_facturadas, p.prosper_cuotas_a_tiempo,
       p.prosper_cuotas_atraso_menor_mes, p.prosper_cuotas_atraso_mes_mas,
       p.prosper_capital_prestado, p.prosper_capital_pendiente,
       d.member_key,
       r.exposicion_castigo, r.recuperacion_total, r.lp_costos_cobranza,
       r.objetivo_a, r.objetivo_b_tasa, r.objetivo_b_monto,
       r.en_modelado, r.conjunto
FROM creditos c
JOIN deudores d                ON d.deudor_id  = c.deudor_id
JOIN perfil_solicitud p        ON p.credito_id = c.credito_id
JOIN resultados_recuperacion r ON r.credito_id = c.credito_id
"""


def leer_base(motor: Engine) -> pd.DataFrame:
    """Lee de PostgreSQL una fila por crédito con entradas, objetivos y conjunto."""
    with motor.connect() as con:
        df = pd.read_sql(text(CONSULTA_BASE), con)
    # NUMERIC de PostgreSQL llega como Decimal: se pasa a float para poder operar
    for col in df.columns:
        if df[col].dtype == object and len(df[col].dropna()) and \
                type(df[col].dropna().iloc[0]).__name__ == "Decimal":
            df[col] = df[col].astype(float)
    for col in ["fecha_originacion", "fecha_cierre", "primera_linea_credito"]:
        df[col] = pd.to_datetime(df[col])
    return df


# --------------------------------------------------------------------------
# Variables derivadas
# --------------------------------------------------------------------------
def saldo_estimado_al_default(monto: pd.Series, tasa_anual: pd.Series,
                              plazo: pd.Series, cuotas_pagadas: pd.Series) -> pd.Series:
    """
    Saldo de capital contractual después de `cuotas_pagadas` cuotas (amortización francesa).
    Usa solo términos del contrato: es una ESTIMACIÓN conocida al entrar a cobranza,
    a diferencia de la pérdida real al castigo (LP_GrossPrincipalLoss), que es fuga.
    """
    r = tasa_anual / 12
    k = cuotas_pagadas.clip(lower=0).clip(upper=plazo)
    factor_k = (1 + r) ** k
    cuota = monto * r / (1 - (1 + r) ** (-plazo))
    saldo = np.where(r > 0,
                     monto * factor_k - cuota * (factor_k - 1) / r,
                     monto * (1 - k / plazo))
    return pd.Series(saldo, index=monto.index).clip(lower=0)


def construir_variables(df: pd.DataFrame) -> pd.DataFrame:
    """
    Devuelve SOLO las variables candidatas (una fila por crédito, mismo índice).
    Cada variable es calculable al momento de entrar a cobranza.
    """
    v = pd.DataFrame(index=df.index)

    # --- Condiciones del crédito ---
    v["monto_original_log"] = np.log1p(df["monto_original"])
    v["cuota_mensual_log"] = np.log1p(df["cuota_mensual"])
    v["tasa_interes"] = df["tasa_interes"]
    v["porcentaje_financiado"] = df["porcentaje_financiado"]
    v["n_inversionistas_log"] = np.log1p(df["n_inversionistas"])
    v["tiene_recomendaciones"] = (df["n_recomendaciones"].fillna(0) > 0).astype(int)
    v["tiene_amigos_inversores"] = (df["n_amigos_inversores"].fillna(0) > 0).astype(int)
    v["proposito"] = (df["proposito_codigo"].astype("Int64").astype("string")
                      .fillna("Sin dato").astype(str))

    # --- Calificación unificada de las dos épocas ---
    calif = df["prosper_rating"].fillna(df["calificacion_antigua"])
    v["calificacion_ord"] = calif.map(ESCALA_CALIFICACION)  # NC y nulos -> NaN

    # --- Comportamiento de pago antes del default ---
    v["cuota_primer_default"] = df["cuota_primer_default"]
    v["proporcion_plazo_pagada"] = (df["cuota_primer_default"] / df["plazo_meses"]).clip(0, 1)
    saldo = saldo_estimado_al_default(df["monto_original"], df["tasa_interes"],
                                      df["plazo_meses"], df["cuota_primer_default"])
    v["saldo_estimado_default_log"] = np.log1p(saldo)
    v["pct_saldo_pendiente_estimado"] = (saldo / df["monto_original"]).clip(0, 1)

    # --- Perfil del deudor al solicitar ---
    v["situacion_laboral"] = (df["situacion_laboral"].map(UNIFICAR_SITUACION_LABORAL)
                              .fillna("Sin dato"))
    v["meses_situacion_laboral"] = df["meses_situacion_laboral"]
    v["propietario_vivienda"] = df["propietario_vivienda"].astype(float)
    v["ingreso_verificable"] = df["ingreso_verificable"].astype(float)
    v["pertenece_grupo"] = df["pertenece_grupo"].astype(float)
    v["ingreso_mensual_log"] = np.log1p(df["ingreso_mensual"].clip(lower=0))
    v["cuota_sobre_ingreso"] = (df["cuota_mensual"] /
                                df["ingreso_mensual"].where(df["ingreso_mensual"] > 0)).clip(upper=2)
    v["relacion_deuda_ingreso"] = df["relacion_deuda_ingreso"].clip(upper=10)
    v["estado_residencia"] = df["estado_residencia"].fillna("Sin dato")
    v["ocupacion"] = df["ocupacion"].fillna("Sin dato")

    # --- Central de riesgo ---
    v["puntaje_bureau"] = (df["puntaje_bureau_min"] + df["puntaje_bureau_max"]) / 2
    v["antiguedad_crediticia_anios"] = ((df["fecha_originacion"] - df["primera_linea_credito"])
                                        .dt.days / 365.25)
    for col in ["lineas_credito_actuales", "lineas_credito_abiertas", "lineas_credito_7_anios",
                "cuentas_rotativas_abiertas", "consultas_6_meses", "consultas_totales",
                "moras_actuales", "moras_7_anios", "registros_publicos_10_anios",
                "registros_publicos_12_meses", "uso_tarjetas", "obligaciones_totales",
                "pct_obligaciones_sin_mora", "obligaciones_6_meses"]:
        v[col] = df[col]
    for col in ["pago_mensual_rotativo", "monto_en_mora_al_solicitar", "saldo_rotativo",
                "cupo_disponible_tarjetas"]:
        v[f"{col}_log"] = np.log1p(df[col].clip(lower=0))

    # --- Historial previo con Prosper (nulo = NO tenía créditos previos) ---
    v["tiene_credito_previo_prosper"] = df["prosper_creditos_previos"].notna().astype(int)
    v["prosper_creditos_previos"] = df["prosper_creditos_previos"].fillna(0)
    facturadas = df["prosper_cuotas_facturadas"]
    v["prosper_pct_cuotas_a_tiempo"] = df["prosper_cuotas_a_tiempo"] / facturadas.where(facturadas > 0)
    v["prosper_cuotas_atraso_mes_mas"] = df["prosper_cuotas_atraso_mes_mas"].fillna(0)
    v["prosper_capital_prestado_log"] = np.log1p(df["prosper_capital_prestado"].fillna(0))

    verificar_sin_fuga(v.columns)
    return v


# --------------------------------------------------------------------------
# Controles anti-fuga y de estabilidad
# --------------------------------------------------------------------------
def verificar_sin_fuga(columnas) -> None:
    """Falla de inmediato si alguna variable está en la lista negra."""
    prohibidas = set(columnas) & COLUMNAS_PROHIBIDAS
    if prohibidas:
        raise ValueError(f"🚨 Fuga de datos: estas columnas no pueden ser variables: {sorted(prohibidas)}")


def diferencia_nulos(v: pd.DataFrame, es_entrenamiento: pd.Series,
                     umbral_pp: float = 20) -> pd.DataFrame:
    """
    Compara el % de nulos de cada variable entre entrenamiento y validación.
    Una diferencia grande indica que la variable depende de la ÉPOCA (p. ej., solo
    existe desde 2009): el modelo aprendería el año en vez del deudor.
    """
    t = pd.DataFrame({
        "pct_nulos_entrenamiento": v[es_entrenamiento].isna().mean() * 100,
        "pct_nulos_validacion": v[~es_entrenamiento].isna().mean() * 100,
    }).round(1)
    t["diferencia_pp"] = (t["pct_nulos_validacion"] - t["pct_nulos_entrenamiento"]).abs()
    t["descartar"] = t["diferencia_pp"] > umbral_pp
    return t.sort_values("diferencia_pp", ascending=False)


def diferencia_categorias(v: pd.DataFrame, es_entrenamiento: pd.Series,
                          umbral: float = 0.30) -> pd.DataFrame:
    """
    Distancia de variación total entre la distribución de cada variable categórica
    en entrenamiento y en validación (0 = idénticas, 1 = sin categorías en común).
    Detecta etiquetas que cambiaron con la época, como 'Full-time' vs 'Employed'.
    """
    filas = []
    for col in v.select_dtypes(exclude="number").columns:
        p_ent = v.loc[es_entrenamiento, col].value_counts(normalize=True)
        p_val = v.loc[~es_entrenamiento, col].value_counts(normalize=True)
        p_ent, p_val = p_ent.align(p_val, fill_value=0)
        dif = (p_ent - p_val).abs()
        filas.append({"variable": col,
                      "distancia_tv": round(0.5 * dif.sum(), 3),
                      "categoria_que_mas_cambia": dif.idxmax(),
                      "pct_ent": round(p_ent[dif.idxmax()] * 100, 1),
                      "pct_val": round(p_val[dif.idxmax()] * 100, 1)})
    t = pd.DataFrame(filas).sort_values("distancia_tv", ascending=False).reset_index(drop=True)
    t["descartar"] = t["distancia_tv"] > umbral
    return t


def auc_univariado(v: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
    """
    AUC de cada variable numérica sola contra el objetivo A (solo entrenamiento).
    Una sola variable con AUC > 0,90 en un problema difícil como este es sospechosa
    de fuga y se revisa a mano.
    """
    from sklearn.metrics import roc_auc_score

    filas = []
    for col in v.select_dtypes("number").columns:
        m = v[col].notna()
        if m.sum() < 100 or v.loc[m, col].nunique() < 2:
            continue
        auc = roc_auc_score(y[m], v.loc[m, col])
        filas.append({"variable": col, "auc": round(max(auc, 1 - auc), 3),
                      "direccion": "+" if auc >= 0.5 else "−",
                      "pct_con_dato": round(m.mean() * 100, 1)})
    t = pd.DataFrame(filas).sort_values("auc", ascending=False).reset_index(drop=True)
    t["sospechosa_fuga"] = t["auc"] > 0.90
    return t


def guardar_contrato(ruta: Path, numericas: list[str], categoricas: list[str],
                     excluidas: dict[str, str]) -> None:
    """
    Guarda la lista de variables que usa el modelo (el 'contrato'). La aplicación
    lo lee para construir exactamente las mismas columnas en el mismo orden.
    """
    ruta.write_text(json.dumps({
        "numericas": numericas,
        "categoricas": categoricas,
        "objetivos": {"A": "objetivo_a", "B": "objetivo_b_tasa"},
        "excluidas": excluidas,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
