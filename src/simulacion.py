"""
Simulación de campañas de cobranza y ROI (Fase 8).

Todo lo relativo a canales es SIMULADO (Prosper no registra gestiones). Supuestos:
  - La recuperación REAL observada en Prosper es lo que logra la gestión más intensiva
    (negociación con asesor, efectividad 1,0).
  - Contactado por el canal c  -> recupera  real × efectividad(c)
  - No contactado              -> recupera  real × RECUPERACION_SIN_GESTION (pago espontáneo)
  - Venta de cartera           -> ingresa   precio × saldo estimado (y renuncia a cobrar)

KPI: USD recuperados de forma INCREMENTAL (por encima de no hacer nada) por cada USD
invertido en cobranza.

Regla anti-trampa: el canal de cada segmento se OPTIMIZA con el ENTRENAMIENTO para el
presupuesto dado;
la comparación de estrategias se mide en la VALIDACIÓN.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.supuestos import CANALES

SUPUESTOS_SIMULACION = {
    "recuperacion_sin_gestion": 0.10,   # fracción que se recupera aunque nadie gestione
    "precio_venta_pct_saldo": 0.04,     # la cartera castigada se vende a ~4 centavos por dólar
}
NO_GESTIONAR = "No gestionar"


def catalogo_canales(mult_costo: float = 1.0, mult_efectividad: float = 1.0) -> pd.DataFrame:
    """Canales con multiplicadores para el análisis de sensibilidad (efectividad máx. 1)."""
    cat = pd.DataFrame(CANALES).set_index("nombre")
    cat["costo"] = cat["costo_por_contacto_usd"] * mult_costo
    cat["efectividad"] = (cat["efectividad_supuesta"] * mult_efectividad).clip(upper=1.0)
    return cat[["canal_id", "costo", "efectividad"]]


def valor_incremental(real: np.ndarray, saldo: np.ndarray, canal: str,
                      cat: pd.DataFrame, sup: dict) -> np.ndarray:
    """USD incrementales (frente a no gestionar) de aplicar `canal`, ya descontado su costo."""
    sg = sup["recuperacion_sin_gestion"]
    if canal == NO_GESTIONAR:
        return np.zeros(len(real))
    if canal == "Venta de cartera":
        return sup["precio_venta_pct_saldo"] * saldo - sg * real
    fila = cat.loc[canal]
    return real * (fila["efectividad"] - sg) - fila["costo"]


def elegir_canal_por_segmento(ent: pd.DataFrame, cat: pd.DataFrame, sup: dict) -> pd.DataFrame:
    """
    Para cada segmento, el canal con mayor valor incremental MEDIO en el ENTRENAMIENTO.
    Si ninguno es positivo -> 'No gestionar'.
    """
    filas = []
    for seg, g in ent.groupby("segmento_id"):
        opciones = {c: valor_incremental(g["recuperacion_total"].to_numpy(),
                                         g["saldo_estimado"].to_numpy(), c, cat, sup).mean()
                    for c in list(cat.index) + [NO_GESTIONAR]}
        mejor = max(opciones, key=opciones.get)
        filas.append({"segmento_id": seg, "canal_elegido": mejor,
                      **{f"valor_{c}": round(v, 2) for c, v in opciones.items()}})
    return pd.DataFrame(filas).set_index("segmento_id")


def orden_modelo(df: pd.DataFrame, canal: pd.Series, cat: pd.DataFrame, sup: dict) -> np.ndarray:
    """
    Orden de gestión según el MODELO: valor incremental esperado por cada USD gastado
    (criterio voraz de la mochila: con presupuesto limitado, primero lo que más rinde por dólar).
    Usa la recuperación ESPERADA (monto_esperado_modelo), nunca la real.
    """
    ve = np.zeros(len(df))
    for c in canal.unique():
        m = (canal == c).to_numpy()
        ve[m] = valor_incremental(df["monto_esperado_modelo"].to_numpy()[m],
                                  df["saldo_estimado"].to_numpy()[m], c, cat, sup)
    costo = canal.map(cat["costo"]).fillna(0).to_numpy()
    return np.argsort(-(ve / np.maximum(costo, 0.01)), kind="stable")


def simular(df: pd.DataFrame, orden: np.ndarray, canal: pd.Series, presupuesto: float,
            cat: pd.DataFrame, sup: dict) -> dict:
    """
    Recorre los créditos en `orden` y los gestiona con su `canal` hasta agotar el presupuesto.
    Devuelve el resumen y el detalle por crédito (para guardar en PostgreSQL).
    """
    d = df.iloc[orden].copy()
    d["canal"] = canal.iloc[orden].to_numpy()
    es_venta, no_gestion = d["canal"].eq("Venta de cartera"), d["canal"].eq(NO_GESTIONAR)
    costo_unit = d["canal"].map(cat["costo"]).fillna(0).to_numpy()
    # La venta no cuesta: se ejecuta siempre que sea el canal asignado
    d["contactado"] = (((np.cumsum(costo_unit) <= presupuesto) | es_venta.to_numpy())
                       & ~no_gestion.to_numpy())
    d["costo_usd"] = np.where(d["contactado"], costo_unit, 0.0)

    real, saldo, sg = d["recuperacion_total"].to_numpy(), d["saldo_estimado"].to_numpy(), sup["recuperacion_sin_gestion"]
    efect = d["canal"].map(cat["efectividad"]).fillna(0).to_numpy()
    d["recuperacion_simulada"] = np.select(
        [d["contactado"] & es_venta, d["contactado"]],
        [sup["precio_venta_pct_saldo"] * saldo, real * efect],
        default=real * sg)

    base_sin_gestion = (real * sg).sum()
    costo = d["costo_usd"].sum()
    incremental = d["recuperacion_simulada"].sum() - base_sin_gestion
    return {
        "resumen": {
            "creditos_gestionados": int(d["contactado"].sum()),
            "costo_usd": round(costo, 2),
            "recuperado_usd": round(d["recuperacion_simulada"].sum(), 2),
            "incremental_usd": round(incremental, 2),
            "neto_usd": round(incremental - costo, 2),
            "usd_por_usd_invertido": round(incremental / costo, 2) if costo > 0 else np.nan,
        },
        "detalle": d,
    }


def optimizar_canales(ent: pd.DataFrame, cat: pd.DataFrame, sup: dict, fraccion: float,
                      pasadas: int = 3) -> pd.Series:
    """
    Elige el canal de cada segmento para un PRESUPUESTO dado, maximizando el beneficio neto
    simulado en el ENTRENAMIENTO (búsqueda por coordenadas: se cambia un segmento a la vez
    y se conserva el cambio si mejora). Parte de la mejor opción por crédito.
    """
    presupuesto = fraccion * len(ent) * cat.loc["Llamada de asesor", "costo"]
    opciones = list(cat.index) + [NO_GESTIONAR]
    asignacion = elegir_canal_por_segmento(ent, cat, sup)["canal_elegido"].to_dict()

    def neto(asig):
        canal = ent["segmento_id"].map(asig)
        return simular(ent, orden_modelo(ent, canal, cat, sup), canal, presupuesto, cat, sup)["resumen"]["neto_usd"]

    mejor = neto(asignacion)
    for _ in range(pasadas):
        cambio = False
        for seg in sorted(asignacion):
            for c in opciones:
                prueba = {**asignacion, seg: c}
                v = neto(prueba)
                if v > mejor + 1e-6:
                    asignacion, mejor, cambio = prueba, v, True
        if not cambio:
            break
    return pd.Series(asignacion, name="canal_optimizado")


def estrategias(val: pd.DataFrame, canal_modelo: pd.Series, presupuesto: float,
                cat: pd.DataFrame, sup: dict, semillas: int = 20) -> pd.DataFrame:
    """Compara las estrategias con el MISMO presupuesto (el azar se promedia en varias semillas)."""
    llamada = pd.Series("Llamada de asesor", index=val.index)
    puntaje = (val["prob_recuperar"] * val["saldo_estimado"]).to_numpy()
    filas = {}

    filas["Sin modelo: todos por llamada (sin límite)"] = simular(
        val, np.arange(len(val)), llamada, np.inf, cat, sup)["resumen"]

    azar = [simular(val, np.random.default_rng(s).permutation(len(val)), llamada, presupuesto, cat, sup)["resumen"]
            for s in range(semillas)]
    filas["Sin modelo: al azar, llamada"] = pd.DataFrame(azar).mean().round(2).to_dict()

    # Mezcla de canales: WhatsApp a todos + llamadas con el presupuesto que sobre.
    # Sin modelo las llamadas van al azar; con modelo, a los de mayor P×saldo esperado.
    # Mismo costo y misma mezcla: la ÚNICA diferencia es A QUIÉN se llama.
    costo_wa = cat.loc["WhatsApp", "costo"] * len(val)
    extra = max(cat.loc["Llamada de asesor", "costo"] - cat.loc["WhatsApp", "costo"], 0.01)
    n_llamadas = min(int(max(presupuesto - costo_wa, 0) // extra), len(val))

    def mezcla(indices_llamada):
        canal_h = pd.Series("WhatsApp", index=val.index)
        canal_h.iloc[indices_llamada] = "Llamada de asesor"
        return simular(val, np.arange(len(val)), canal_h, presupuesto, cat, sup)["resumen"]

    hib = [mezcla(np.random.default_rng(s).permutation(len(val))[:n_llamadas]) for s in range(semillas)]
    filas["Sin modelo: WhatsApp a todos + llamadas al azar"] = pd.DataFrame(hib).mean().round(2).to_dict()

    filas["Con modelo: prioriza por P×saldo, llamada"] = simular(
        val, np.argsort(-puntaje, kind="stable"), llamada, presupuesto, cat, sup)["resumen"]

    filas["Con modelo: WhatsApp a todos + llamadas priorizadas"] = mezcla(
        np.argsort(-puntaje, kind="stable")[:n_llamadas])

    filas["Con modelo: prioriza + canal por segmento"] = simular(
        val, orden_modelo(val, canal_modelo, cat, sup), canal_modelo, presupuesto, cat, sup)["resumen"]
    return pd.DataFrame(filas).T
