"""
Servicio de predicción para la aplicación (Fase 9).

Toda la lógica que la aplicación necesita vive aquí (y no en app/app.py), para que sea
probable con pytest y para que la app sea solo la interfaz.

La aplicación se conecta con el rol de SOLO LECTURA (lector_bi) y lee:
  - vw_entradas_modelo  : entradas del modelo, sin desenlace ni identificadores de persona
  - vw_cartera_cobranza : predicciones vigentes, segmento y acción
  - segmentos           : catálogo de acciones
"""
from __future__ import annotations

import json
from decimal import Decimal

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.config import RUTAS
from src.variables import construir_variables, saldo_al_default

# Nombres legibles para explicar el modelo a un usuario de negocio
NOMBRES = {
    "cuota_primer_default": "Cuota en la que cayó en default",
    "proporcion_plazo_pagada": "Proporción del plazo pagada antes del default",
    "pct_saldo_pendiente_estimado": "% del crédito pendiente al default",
    "saldo_estimado_default_log": "Saldo estimado al default",
    "moras_7_anios": "Moras en los últimos 7 años",
    "moras_actuales": "Moras vigentes al solicitar",
    "lineas_credito_7_anios": "Líneas de crédito en 7 años",
    "ingreso_mensual_log": "Ingreso mensual",
    "relacion_deuda_ingreso": "Relación deuda / ingreso",
    "cuota_sobre_ingreso": "Cuota / ingreso",
    "consultas_totales": "Consultas a la central de riesgo",
    "consultas_6_meses": "Consultas en 6 meses",
    "pago_mensual_rotativo_log": "Pago mensual en tarjetas y cupos",
    "n_inversionistas_log": "Número de inversionistas",
    "antiguedad_crediticia_anios": "Antigüedad crediticia (años)",
    "calificacion_ord": "Calificación de riesgo (1 = HR … 7 = AA)",
    "puntaje_bureau": "Puntaje de la central de riesgo",
    "monto_original_log": "Monto del crédito",
    "tasa_interes": "Tasa de interés",
    "cuentas_rotativas_abiertas": "Cuentas rotativas abiertas",
    "propietario_vivienda": "Es propietario de vivienda",
    "ingreso_verificable": "Ingreso verificable",
    "tiene_credito_previo_prosper": "Tenía créditos previos con Prosper",
}

COLUMNAS_FECHA = ["fecha_originacion", "primera_linea_credito"]
COLUMNAS_TEXTO = {"loan_key", "conjunto", "prosper_rating", "calificacion_antigua", "estado_residencia",
                  "ocupacion", "situacion_laboral", "rango_ingresos"}


def _a_float(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte a número todo lo que no es texto ni fecha. Necesario porque NUMERIC llega
    como Decimal y, si se lee UN solo crédito con un dato vacío, la columna llega como None.
    """
    for col in df.columns:
        if col in COLUMNAS_TEXTO or col in COLUMNAS_FECHA or df[col].dtype == bool:
            continue
        if df[col].dtype == object:
            df[col] = pd.to_numeric(df[col].map(lambda v: float(v) if isinstance(v, (Decimal, bool)) else v),
                                    errors="coerce")
    for col in COLUMNAS_FECHA:
        if col in df:
            df[col] = pd.to_datetime(df[col])
    return df


# --------------------------------------------------------------------------
# Artefactos y datos
# --------------------------------------------------------------------------
def cargar_artefactos() -> dict:
    """Modelo A, segmentador y métricas guardados por los notebooks 06 a 08."""
    faltan = [f for f in ["modelo_A.joblib", "segmentador.joblib", "metricas.json"]
              if not (RUTAS["models"] / f).exists()]
    if faltan:
        raise FileNotFoundError(f"Faltan archivos en models/: {faltan}. Ejecuta los notebooks 06 y 07.")
    metricas = json.loads((RUTAS["models"] / "metricas.json").read_text(encoding="utf-8"))
    return {
        "modelo": joblib.load(RUTAS["models"] / "modelo_A.joblib"),
        "segmentador": joblib.load(RUTAS["models"] / "segmentador.joblib"),
        "tasa_media": metricas["segmentacion"]["tasa_media_entrenamiento"],
        "ratio_saldo": metricas["ratio_saldo_mediano"],
        "metricas": metricas,
    }


def leer_entradas(motor: Engine, credito_id: int | None = None) -> pd.DataFrame:
    """Entradas del modelo desde la vista de solo lectura (uno o todos los créditos)."""
    sql = "SELECT * FROM vw_entradas_modelo"
    params = {}
    if credito_id is not None:
        sql += " WHERE credito_id = :id"
        params["id"] = int(credito_id)
    with motor.connect() as con:
        return _a_float(pd.read_sql(text(sql), con, params=params))


# --------------------------------------------------------------------------
# Predicción, explicación y alertas
# --------------------------------------------------------------------------
def evaluar(entradas: pd.DataFrame, art: dict) -> pd.DataFrame:
    """P(recuperar), saldo estimado, monto esperado y segmento para cada fila."""
    X = construir_variables(entradas)
    salida = entradas[["credito_id"]].copy() if "credito_id" in entradas else pd.DataFrame(index=entradas.index)
    salida["prob_recuperar"] = art["modelo"].predict_proba(X)
    saldo = saldo_al_default(entradas)
    salida["saldo_imputado"] = saldo.isna().to_numpy()
    salida["saldo_estimado"] = saldo.fillna(entradas["monto_original"] * art["ratio_saldo"]).to_numpy()
    salida["monto_esperado"] = salida["prob_recuperar"] * art["tasa_media"] * salida["saldo_estimado"]
    para_seg = pd.DataFrame({"prob_recuperar": salida["prob_recuperar"].to_numpy(),
                             "saldo_log": np.log1p(salida["saldo_estimado"].to_numpy()),
                             "cuota_primer_default": entradas["cuota_primer_default"].to_numpy()})
    salida["segmento_id"] = art["segmentador"].predict(para_seg)
    return salida


def explicar(entradas: pd.DataFrame, art: dict, top: int = 8) -> pd.DataFrame:
    """
    Contribución SHAP de cada variable para UN crédito (escala log-odds del modelo):
    positivo = sube la probabilidad de recuperar; negativo = la baja.
    """
    import shap

    modelo = art["modelo"]
    X = modelo._preparar(construir_variables(entradas).iloc[[0]])
    valores = shap.TreeExplainer(modelo.estimador_).shap_values(X)
    valores = valores[1] if isinstance(valores, list) else valores
    t = pd.DataFrame({"variable": X.columns, "valor": X.iloc[0].to_numpy(), "contribucion": valores[0]})
    t["nombre"] = t["variable"].map(NOMBRES).fillna(t["variable"])
    return t.reindex(t["contribucion"].abs().sort_values(ascending=False).index).head(top).reset_index(drop=True)


def alertas(fila: pd.Series) -> list[str]:
    """Advertencias de uso responsable para un crédito concreto."""
    msgs = []
    if pd.notna(fila.get("cuota_primer_default")) and fila["cuota_primer_default"] <= 1:
        msgs.append("🚩 Default en la primera cuota: patrón típico de fraude. Verificar identidad antes de cobrar.")
    if fila.get("plazo_meses") != 36:
        msgs.append(f"⚠️ Plazo de {fila.get('plazo_meses')} meses: el modelo se entrenó con créditos a 36 meses; "
                    "la predicción es una extrapolación.")
    if pd.isna(fila.get("cuota_primer_default")):
        msgs.append("ℹ️ Sin dato de la cuota de default: el saldo se estimó con la mediana de la cartera.")
    return msgs
