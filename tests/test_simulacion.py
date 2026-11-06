"""Pruebas de la simulación de campañas (Fase 8)."""
import numpy as np
import pandas as pd

from src.simulacion import catalogo_canales, simular

SUP = {"recuperacion_sin_gestion": 0.10, "precio_venta_pct_saldo": 0.04}


def _cartera(n=10):
    return pd.DataFrame({"credito_id": range(n), "recuperacion_total": np.full(n, 100.0),
                         "saldo_estimado": np.full(n, 1000.0)})


def test_no_se_gasta_mas_que_el_presupuesto():
    df, cat = _cartera(), catalogo_canales()
    canal = pd.Series("Llamada de asesor", index=df.index)
    res = simular(df, np.arange(len(df)), canal, presupuesto=10, cat=cat, sup=SUP)
    assert res["resumen"]["costo_usd"] <= 10
    assert res["resumen"]["creditos_gestionados"] == 3      # 3 llamadas de USD 3


def test_sin_presupuesto_solo_hay_pago_espontaneo():
    df, cat = _cartera(), catalogo_canales()
    canal = pd.Series("Llamada de asesor", index=df.index)
    res = simular(df, np.arange(len(df)), canal, presupuesto=0, cat=cat, sup=SUP)
    assert res["resumen"]["incremental_usd"] == 0
    assert res["resumen"]["recuperado_usd"] == 100.0          # 10 créditos × 100 × 10 %


def test_la_venta_no_consume_presupuesto():
    df, cat = _cartera(), catalogo_canales()
    canal = pd.Series("Venta de cartera", index=df.index)
    res = simular(df, np.arange(len(df)), canal, presupuesto=0, cat=cat, sup=SUP)
    assert res["resumen"]["creditos_gestionados"] == 10
    assert res["resumen"]["recuperado_usd"] == 400.0          # 10 × 4 % × 1000
