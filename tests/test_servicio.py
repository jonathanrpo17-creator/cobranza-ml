"""Pruebas de las alertas de uso responsable de la aplicación."""
import numpy as np
import pandas as pd

from src.servicio import alertas


def test_alerta_de_fraude_en_primera_cuota():
    msgs = alertas(pd.Series({"cuota_primer_default": 1, "plazo_meses": 36}))
    assert any("fraude" in m for m in msgs)


def test_alerta_de_extrapolacion_por_plazo():
    msgs = alertas(pd.Series({"cuota_primer_default": 12, "plazo_meses": 60}))
    assert any("36 meses" in m for m in msgs)


def test_sin_alertas_en_un_caso_normal():
    assert alertas(pd.Series({"cuota_primer_default": 12, "plazo_meses": 36})) == []


def test_aviso_de_saldo_imputado():
    msgs = alertas(pd.Series({"cuota_primer_default": np.nan, "plazo_meses": 36}))
    assert any("mediana" in m for m in msgs)


def test_conversion_de_un_credito_con_datos_vacios():
    """Un solo crédito con un dato NULL llega como None: debe quedar como NaN numérico."""
    from decimal import Decimal
    from src.servicio import _a_float
    df = pd.DataFrame({"saldo_rotativo": [None], "monto_original": [Decimal("1000.50")],
                       "propietario_vivienda": [True], "ocupacion": ["Other"]})
    out = _a_float(df)
    assert np.isnan(out.loc[0, "saldo_rotativo"])
    assert out.loc[0, "monto_original"] == 1000.5
    assert out.loc[0, "ocupacion"] == "Other"
