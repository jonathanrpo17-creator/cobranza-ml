"""
Métricas técnicas y de negocio (Fase 6).

Además de las métricas estándar (AUC, PR-AUC, Brier, MAE...), aquí están las que
importan para cobranza: si ordeno la cartera por el puntaje del modelo y contacto
primero a los de arriba, ¿cuánto del dinero recuperable capturo con menos contactos?
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, brier_score_loss, mean_absolute_error,
                             mean_squared_error, r2_score, roc_auc_score)


def metricas_clasificacion(y, p, nombre: str) -> dict:
    """AUC-ROC, PR-AUC (comparada con la tasa base) y Brier."""
    y = np.asarray(y)
    return {
        "modelo": nombre,
        "auc_roc": round(roc_auc_score(y, p), 4),
        "pr_auc": round(average_precision_score(y, p), 4),
        "pr_auc_azar": round(y.mean(), 4),          # PR-AUC de un modelo al azar = tasa base
        "brier": round(brier_score_loss(y, p), 4),
        "brier_tasa_base": round(brier_score_loss(y, np.full(len(y), y.mean())), 4),
        "prob_media": round(float(np.mean(p)), 4),
        "tasa_real": round(float(y.mean()), 4),
    }


def metricas_regresion(y, pred, nombre: str) -> dict:
    return {
        "modelo": nombre,
        "mae": round(mean_absolute_error(y, pred), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(y, pred))), 4),
        "r2": round(r2_score(y, pred), 4),
    }


def tabla_deciles(puntaje, y, recuperado_usd, n: int = 10) -> pd.DataFrame:
    """
    Ordena de mayor a menor puntaje y parte en deciles (1 = el 10 % más prometedor).
    lift = tasa del decil / tasa promedio. Un lift de 2 en el decil 1 significa que
    ahí se recupera el doble que contactando al azar.
    """
    df = pd.DataFrame({"p": np.asarray(puntaje), "y": np.asarray(y),
                       "usd": np.asarray(recuperado_usd)})
    df = df.sort_values("p", ascending=False).reset_index(drop=True)
    df["decil"] = (np.arange(len(df)) * n // len(df)) + 1
    t = df.groupby("decil").agg(creditos=("y", "size"), puntaje_medio=("p", "mean"),
                                tasa_recupera=("y", "mean"), usd_recuperado=("usd", "sum"))
    t["lift"] = t["tasa_recupera"] / df["y"].mean()
    t["pct_recuperadores_acum"] = t["tasa_recupera"].mul(t["creditos"]).cumsum() / df["y"].sum()
    t["pct_usd_acum"] = t["usd_recuperado"].cumsum() / df["usd"].sum()
    return t.round(4)


def curva_ganancia(puntaje, valor) -> tuple[np.ndarray, np.ndarray]:
    """
    Eje x: % de la cartera contactada (de mayor a menor puntaje).
    Eje y: % del valor total (créditos recuperados o USD) capturado.
    """
    orden = np.argsort(-np.asarray(puntaje), kind="stable")
    v = np.asarray(valor, dtype=float)[orden]
    x = np.arange(1, len(v) + 1) / len(v)
    return np.insert(x, 0, 0), np.insert(np.cumsum(v) / v.sum(), 0, 0)


def captura_en(puntaje, valor, fraccion: float = 0.2) -> float:
    """% del valor total capturado contactando solo la `fraccion` superior."""
    x, y = curva_ganancia(puntaje, valor)
    return float(np.interp(fraccion, x, y))
