"""
Depuración, población objetivo y variables objetivo (Fase 3).

Definiciones (momento de predicción = entrada a cobranza):
- Exposición al castigo: capital pendiente cuando el crédito se castigó
  = LP_GrossPrincipalLoss.
- Recuperación de capital posterior al castigo
  = LP_GrossPrincipalLoss - LP_NetPrincipalLoss.
- Recuperación total = recuperación de capital + LP_NonPrincipalRecoverypayments.
- Objetivo A (clasificación): 1 si la recuperación total >= umbral (USD), si no 0.
- Objetivo B (regresión): tasa de recuperación = recuperación total / exposición.
  También se guarda el monto en USD.

Estas columnas LP_* son FUGA: se usan aquí para construir el objetivo y nunca
como predictoras (ver src/diccionario.py).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ESTADOS_OBJETIVO = ["Chargedoff", "Defaulted"]
UMBRAL_RECUPERACION_USD = 1.0  # evita contar centavos de ajustes contables como "recuperación"
# Meses mínimos de observación después del castigo para considerar "conocido" el desenlace.
# Se valida con la curva de maduración del notebook 03 (sección 8b).
VENTANA_MADURACION_MESES = 24


# --------------------------------------------------------------------------
# Duplicados
# --------------------------------------------------------------------------
def diagnosticar_duplicados(df: pd.DataFrame, llave: str = "LoanKey") -> pd.Series:
    """
    Para los créditos repetidos, cuenta en cuántos grupos cambia cada columna.
    Sirve para entender POR QUÉ se repiten antes de decidir cuál fila conservar.
    """
    repetidos = df[df[llave].duplicated(keep=False)]
    if repetidos.empty:
        return pd.Series(dtype=int)
    cambia = repetidos.groupby(llave).nunique(dropna=False) > 1
    resumen = cambia.sum()
    return resumen[resumen > 0].sort_values(ascending=False)


def depurar_duplicados(df: pd.DataFrame, llave: str = "LoanKey") -> pd.DataFrame:
    """
    Deja una fila por crédito.

    Diagnóstico (notebook 03, sección 2): las filas repetidas de un mismo LoanKey
    solo difieren en ProsperScore. Como no hay forma de saber cuál es el valor
    correcto, se aplica una regla CONSERVADORA: conservar el ProsperScore más bajo
    (en Prosper, menor puntaje = mayor riesgo).
    """
    antes = len(df)
    salida = (df.sort_values([llave, "ProsperScore"], kind="stable", na_position="last")
                .drop_duplicates(subset=llave, keep="first")
                .reset_index(drop=True))
    print(f"Filas antes: {antes:,} | después: {len(salida):,} | eliminadas: {antes - len(salida):,}")
    return salida


# --------------------------------------------------------------------------
# Población
# --------------------------------------------------------------------------
def seleccionar_poblacion(df: pd.DataFrame) -> pd.DataFrame:
    """Créditos en dificultad con desenlace conocido (Chargedoff o Defaulted)."""
    pob = df[df["LoanStatus"].isin(ESTADOS_OBJETIVO)].copy()
    print(f"Población objetivo: {len(pob):,} créditos "
          f"({len(pob) / len(df):.1%} del total depurado)")
    return pob


# --------------------------------------------------------------------------
# Chequeos de consistencia ANTES de construir el objetivo
# --------------------------------------------------------------------------
def chequeos_consistencia(pob: pd.DataFrame) -> pd.DataFrame:
    """
    Verifica que las columnas LP_* se comporten como esperamos, por estado.
    Si algo no cuadra (p. ej., exposición en cero), se ve aquí y se decide.
    """
    gross, net = pob["LP_GrossPrincipalLoss"], pob["LP_NetPrincipalLoss"]
    otros = pob["LP_NonPrincipalRecoverypayments"]
    chequeos = pd.DataFrame({
        "LoanStatus": pob["LoanStatus"],
        "exposicion_cero_o_negativa": gross <= 0,
        "neta_mayor_que_bruta": net > gross,          # recuperación negativa: raro
        "recupera_capital": (gross - net) > 0,
        "recupera_no_capital": otros > 0,
        "no_capital_negativo": otros < 0,
        "closeddate_nula": pob["ClosedDate"].isna(),
    })
    tabla = chequeos.groupby("LoanStatus").mean().mul(100).round(2)
    tabla.insert(0, "creditos", chequeos.groupby("LoanStatus").size())
    tabla.loc["TOTAL"] = [len(chequeos)] + (chequeos.drop(columns="LoanStatus").mean()
                                             .mul(100).round(2).tolist())
    return tabla


# --------------------------------------------------------------------------
# Variables objetivo
# --------------------------------------------------------------------------
def construir_objetivos(pob: pd.DataFrame,
                        umbral: float = UMBRAL_RECUPERACION_USD) -> pd.DataFrame:
    """
    Agrega exposición, recuperación y los objetivos A y B a la población.

    Decisiones (respaldadas por los chequeos de la sección 5 del notebook 03):
    - Si la pérdida neta supera la bruta, la recuperación de capital se toma como 0
      (no existe recuperación negativa).
    - La tasa B se acota a [0, 1]: los casos > 100 % ocurren porque las recuperaciones
      que no son capital se suman sobre la exposición de capital.
    - Créditos sin exposición (bruta <= 0) no tienen nada que recuperar: quedan
      marcados con exposicion_valida = False y se excluyen del modelado.
    """
    pob = pob.copy()
    gross = pob["LP_GrossPrincipalLoss"]
    net = pob["LP_NetPrincipalLoss"]

    pob["exposicion_castigo"] = gross
    pob["recuperacion_capital"] = (gross - net).clip(lower=0)
    pob["recuperacion_no_capital"] = pob["LP_NonPrincipalRecoverypayments"].clip(lower=0)
    pob["recuperacion_total"] = pob["recuperacion_capital"] + pob["recuperacion_no_capital"]

    pob["exposicion_valida"] = gross > 0
    tasa_sin_tope = pob["recuperacion_total"] / gross.where(gross > 0)
    pob["recuperacion_supera_exposicion"] = tasa_sin_tope > 1

    pob["objetivo_A"] = (pob["recuperacion_total"] >= umbral).astype(int)
    pob["objetivo_B_tasa"] = tasa_sin_tope.clip(lower=0, upper=1)
    # Monto coherente con la tasa acotada (es lo que se modela).
    # Para el ROI real se usa recuperacion_total (dinero efectivamente recibido).
    pob["objetivo_B_monto"] = pob["objetivo_B_tasa"] * gross.where(gross > 0)
    return pob


# --------------------------------------------------------------------------
# Censura: ventana de maduración
# --------------------------------------------------------------------------
def marcar_madurez(pob: pd.DataFrame, fecha_corte: pd.Timestamp,
                   ventana_meses: int = VENTANA_MADURACION_MESES) -> pd.DataFrame:
    """
    Un crédito castigado poco antes de la extracción de los datos no ha tenido
    tiempo de mostrar sus recuperaciones (censura). Se marca como 'maduro' solo si
    tuvo al menos `ventana_meses` de observación después del cierre.

    ClosedDate se usa aquí SOLO para definir la población, nunca como predictora.
    """
    pob = pob.copy()
    pob["meses_observacion"] = (fecha_corte - pob["ClosedDate"]).dt.days / 30.44
    pob["madura"] = pob["meses_observacion"] >= ventana_meses
    pob["en_modelado"] = pob["madura"] & pob["exposicion_valida"]
    return pob


def curva_maduracion(pob: pd.DataFrame, paso_meses: int = 6) -> pd.DataFrame:
    """% que recupera algo según los meses de observación después del cierre."""
    bordes = np.arange(0, pob["meses_observacion"].max() + paso_meses, paso_meses)
    tramo = pd.cut(pob["meses_observacion"], bordes, right=False)
    t = pob.groupby(tramo, observed=True).agg(
        creditos=("objetivo_A", "size"),
        pct_recupera=("objetivo_A", "mean"),
        exposicion=("exposicion_castigo", "sum"),
        recuperado=("recuperacion_total", "sum"),
    )
    t["pct_recupera"] = (t["pct_recupera"] * 100).round(1)
    t["tasa_cartera_pct"] = (t["recuperado"] / t["exposicion"].where(t["exposicion"] > 0) * 100).round(1)
    t.index = t.index.astype(str)
    t.index.name = "meses_observacion"
    return t.drop(columns=["exposicion", "recuperado"])


def sensibilidad_ventana(pob: pd.DataFrame, ventanas=(12, 18, 24, 30, 36)) -> pd.DataFrame:
    """Cuántos créditos quedan para modelar según la ventana de maduración elegida."""
    filas = []
    for v in ventanas:
        m = (pob["meses_observacion"] >= v) & pob["exposicion_valida"]
        filas.append({
            "ventana_meses": v,
            "creditos_modelado": int(m.sum()),
            "pct_poblacion": round(m.mean() * 100, 1),
            "pct_recupera_A": round(pob.loc[m, "objetivo_A"].mean() * 100, 1),
            "creditos_inmaduros": int((~m & pob["exposicion_valida"]).sum()),
        })
    return pd.DataFrame(filas).set_index("ventana_meses")


def resumen_objetivos(pob: pd.DataFrame) -> pd.DataFrame:
    """Indicadores principales de los objetivos, por estado y total."""
    def _resumen(g: pd.DataFrame) -> pd.Series:
        recuperan = g[g["objetivo_A"] == 1]
        return pd.Series({
            "creditos": len(g),
            "pct_exposicion_valida": round(g["exposicion_valida"].mean() * 100, 2),
            "pct_recupera_algo (A=1)": round(g["objetivo_A"].mean() * 100, 2),
            "exposicion_total_usd": round(g["exposicion_castigo"].sum(), 0),
            "recuperado_total_usd": round(g["recuperacion_total"].sum(), 0),
            "tasa_recuperacion_cartera_pct": round(
                g["recuperacion_total"].sum() / g["exposicion_castigo"].clip(lower=0).sum() * 100, 2)
                if g["exposicion_castigo"].clip(lower=0).sum() > 0 else np.nan,
            "tasa_mediana_si_recupera_pct": round(recuperan["objetivo_B_tasa"].median() * 100, 2),
            "pct_tasa_mayor_100": round(g["recuperacion_supera_exposicion"].mean() * 100, 2),
        })
    por_estado = pob.groupby("LoanStatus").apply(_resumen, include_groups=False)
    por_estado.loc["TOTAL"] = _resumen(pob)
    return por_estado
