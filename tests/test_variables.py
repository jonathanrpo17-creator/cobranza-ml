"""
Pruebas automáticas de la ingeniería de variables.
Ejecutar desde la raíz del proyecto:   pytest -v
"""
import numpy as np
import pandas as pd
import pytest

from src.variables import (COLUMNAS_PROHIBIDAS, UNIFICAR_SITUACION_LABORAL,
                           saldo_al_default, saldo_estimado_al_default, verificar_sin_fuga)


def test_lista_negra_detecta_fuga():
    """Si una columna de desenlace se cuela como variable, debe fallar."""
    with pytest.raises(ValueError):
        verificar_sin_fuga(["tasa_interes", "recuperacion_total"])


def test_lista_negra_acepta_variables_validas():
    verificar_sin_fuga(["tasa_interes", "ingreso_mensual_log"])


def test_lista_negra_incluye_objetivos_e_identificadores():
    for col in ["objetivo_a", "objetivo_b_tasa", "estado_credito", "fecha_cierre", "loan_key"]:
        assert col in COLUMNAS_PROHIBIDAS


def test_saldo_sin_pagos_es_el_monto():
    s = saldo_estimado_al_default(pd.Series([10000.0]), pd.Series([0.12]),
                                  pd.Series([36]), pd.Series([0.0]))
    assert s.iloc[0] == pytest.approx(10000, rel=1e-6)


def test_saldo_al_final_del_plazo_es_cero():
    s = saldo_estimado_al_default(pd.Series([10000.0]), pd.Series([0.12]),
                                  pd.Series([36]), pd.Series([36.0]))
    assert s.iloc[0] == pytest.approx(0, abs=1e-6)


def test_saldo_disminuye_con_las_cuotas():
    cuotas = pd.Series([0.0, 6, 12, 24, 35])
    s = saldo_estimado_al_default(pd.Series([10000.0] * 5), pd.Series([0.2] * 5),
                                  pd.Series([36] * 5), cuotas)
    assert s.is_monotonic_decreasing


def test_saldo_con_tasa_cero_es_lineal():
    s = saldo_estimado_al_default(pd.Series([3600.0]), pd.Series([0.0]),
                                  pd.Series([36]), pd.Series([18.0]))
    assert s.iloc[0] == pytest.approx(1800)


def test_unificacion_laboral_junta_las_dos_epocas():
    assert UNIFICAR_SITUACION_LABORAL["Full-time"] == UNIFICAR_SITUACION_LABORAL["Employed"]


def test_saldo_al_default_nunca_es_cero_tras_el_vencimiento():
    """Un crédito que cae en default después del plazo debe al menos las cuotas impagas."""
    df = pd.DataFrame({"monto_original": [10000.0], "tasa_interes": [0.2], "plazo_meses": [36],
                       "cuota_primer_default": [40.0], "cuota_mensual": [0.0]})  # cuota reportada en 0
    assert saldo_al_default(df).iloc[0] == pytest.approx(4 * 371.64, rel=1e-3)


def test_saldo_al_default_respeta_nulos():
    df = pd.DataFrame({"monto_original": [10000.0], "tasa_interes": [0.2], "plazo_meses": [36],
                       "cuota_primer_default": [np.nan], "cuota_mensual": [371.6]})
    assert np.isnan(saldo_al_default(df).iloc[0])
