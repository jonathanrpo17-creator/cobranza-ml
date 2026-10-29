"""
Base de datos PostgreSQL: creación, carga y validación (Fase 4).

Flujo:
    crear_base_si_no_existe()  -> crea la base 'cobranza' si no existe
    ejecutar_sql(engine, archivo) -> ejecuta los scripts de sql/ en orden
    preparar_tablas(pob)       -> convierte el DataFrame en las 5 tablas del modelo
    cargar_tablas(engine, tablas) -> inserta respetando las llaves foráneas
    validar_carga(engine, tablas) -> compara conteos y sumas pandas vs PostgreSQL

Los nombres de columnas pasan de inglés (Prosper) a español en snake_case para que
el dashboard y la aplicación sean legibles para el negocio.
"""
from __future__ import annotations

import os

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.config import RUTAS, obtener_url_postgres

# --------------------------------------------------------------------------
# Mapeo de columnas Prosper -> tablas del modelo relacional
# --------------------------------------------------------------------------
MAPEO_CREDITOS = {
    "LoanKey": "loan_key",
    "ListingKey": "listing_key",
    "ListingCreationDate": "fecha_solicitud",
    "LoanOriginationDate": "fecha_originacion",
    "LoanOriginationQuarter": "trimestre_originacion",
    "Term": "plazo_meses",
    "LoanOriginalAmount": "monto_original",
    "MonthlyLoanPayment": "cuota_mensual",
    "BorrowerAPR": "tasa_apr",
    "BorrowerRate": "tasa_interes",
    "LenderYield": "rendimiento_inversionista",
    "ListingCategory (numeric)": "proposito_codigo",
    "PercentFunded": "porcentaje_financiado",
    "Investors": "n_inversionistas",
    "Recommendations": "n_recomendaciones",
    "InvestmentFromFriendsCount": "n_amigos_inversores",
    "InvestmentFromFriendsAmount": "monto_amigos",
    "CreditGrade": "calificacion_antigua",
    "ProsperRating (numeric)": "prosper_rating_num",
    "ProsperRating (Alpha)": "prosper_rating",
    "ProsperScore": "prosper_score",
    "EstimatedEffectiveYield": "rendimiento_estimado",
    "EstimatedLoss": "perdida_estimada",
    "EstimatedReturn": "retorno_estimado",
    "LoanFirstDefaultedCycleNumber": "cuota_primer_default",
    "LoanStatus": "estado_credito",
    "ClosedDate": "fecha_cierre",
}

MAPEO_PERFIL = {
    "DateCreditPulled": "fecha_consulta_bureau",
    "BorrowerState": "estado_residencia",
    "Occupation": "ocupacion",
    "EmploymentStatus": "situacion_laboral",
    "EmploymentStatusDuration": "meses_situacion_laboral",
    "IsBorrowerHomeowner": "propietario_vivienda",
    "CurrentlyInGroup": "pertenece_grupo",
    "GroupKey": "group_key",
    "IncomeRange": "rango_ingresos",
    "IncomeVerifiable": "ingreso_verificable",
    "StatedMonthlyIncome": "ingreso_mensual",
    "DebtToIncomeRatio": "relacion_deuda_ingreso",
    "CreditScoreRangeLower": "puntaje_bureau_min",
    "CreditScoreRangeUpper": "puntaje_bureau_max",
    "FirstRecordedCreditLine": "primera_linea_credito",
    "CurrentCreditLines": "lineas_credito_actuales",
    "OpenCreditLines": "lineas_credito_abiertas",
    "TotalCreditLinespast7years": "lineas_credito_7_anios",
    "OpenRevolvingAccounts": "cuentas_rotativas_abiertas",
    "OpenRevolvingMonthlyPayment": "pago_mensual_rotativo",
    "InquiriesLast6Months": "consultas_6_meses",
    "TotalInquiries": "consultas_totales",
    "CurrentDelinquencies": "moras_actuales",
    "AmountDelinquent": "monto_en_mora_al_solicitar",
    "DelinquenciesLast7Years": "moras_7_anios",
    "PublicRecordsLast10Years": "registros_publicos_10_anios",
    "PublicRecordsLast12Months": "registros_publicos_12_meses",
    "RevolvingCreditBalance": "saldo_rotativo",
    "BankcardUtilization": "uso_tarjetas",
    "AvailableBankcardCredit": "cupo_disponible_tarjetas",
    "TotalTrades": "obligaciones_totales",
    "TradesNeverDelinquent (percentage)": "pct_obligaciones_sin_mora",
    "TradesOpenedLast6Months": "obligaciones_6_meses",
    "ScorexChangeAtTimeOfListing": "cambio_puntaje_desde_ultimo",
    "TotalProsperLoans": "prosper_creditos_previos",
    "TotalProsperPaymentsBilled": "prosper_cuotas_facturadas",
    "OnTimeProsperPayments": "prosper_cuotas_a_tiempo",
    "ProsperPaymentsLessThanOneMonthLate": "prosper_cuotas_atraso_menor_mes",
    "ProsperPaymentsOneMonthPlusLate": "prosper_cuotas_atraso_mes_mas",
    "ProsperPrincipalBorrowed": "prosper_capital_prestado",
    "ProsperPrincipalOutstanding": "prosper_capital_pendiente",
}

MAPEO_RESULTADOS = {
    "LP_CustomerPayments": "lp_pagos_cliente",
    "LP_CustomerPrincipalPayments": "lp_pagos_capital_cliente",
    "LP_InterestandFees": "lp_intereses_cargos",
    "LP_ServiceFees": "lp_comisiones_servicio",
    "LP_CollectionFees": "lp_costos_cobranza",
    "LP_GrossPrincipalLoss": "lp_perdida_bruta_capital",
    "LP_NetPrincipalLoss": "lp_perdida_neta_capital",
    "LP_NonPrincipalRecoverypayments": "lp_recuperacion_no_capital",
    "exposicion_castigo": "exposicion_castigo",
    "recuperacion_capital": "recuperacion_capital",
    "recuperacion_no_capital": "recuperacion_no_capital",
    "recuperacion_total": "recuperacion_total",
    "recuperacion_supera_exposicion": "recuperacion_supera_exposicion",
    "objetivo_A": "objetivo_a",
    "objetivo_B_tasa": "objetivo_b_tasa",
    "objetivo_B_monto": "objetivo_b_monto",
    "meses_observacion": "meses_observacion",
    "exposicion_valida": "exposicion_valida",
    "madura": "madura",
    "en_modelado": "en_modelado",
    "conjunto": "conjunto",
}

ORDEN_CARGA = ["deudores", "creditos", "perfil_solicitud", "resultados_recuperacion"]


# --------------------------------------------------------------------------
# Conexión y ejecución de scripts
# --------------------------------------------------------------------------
def crear_base_si_no_existe() -> None:
    """Se conecta a la base 'postgres' (siempre existe) y crea PG_DB si falta."""
    nombre = os.getenv("PG_DB")
    motor = create_engine(obtener_url_postgres(base="postgres"), isolation_level="AUTOCOMMIT")
    with motor.connect() as con:
        existe = con.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": nombre}).scalar()
        if existe:
            print(f"La base '{nombre}' ya existe.")
        else:
            # TEMPLATE template0 + UTF8: evita problemas de codificación en Windows
            con.exec_driver_sql(f'CREATE DATABASE "{nombre}" ENCODING \'UTF8\' TEMPLATE template0')
            print(f"✅ Base '{nombre}' creada.")
    motor.dispose()


def obtener_motor(rol: str = "admin") -> Engine:
    """Motor de SQLAlchemy para la base del proyecto."""
    return create_engine(obtener_url_postgres(rol=rol))


def ejecutar_sql(motor: Engine, archivo: str) -> None:
    """Ejecuta un script completo de la carpeta sql/ dentro de una transacción."""
    ruta = RUTAS["sql"] / archivo
    with motor.begin() as con:
        con.exec_driver_sql(ruta.read_text(encoding="utf-8"))
    print(f"✅ Ejecutado sql/{archivo}")


def crear_rol_lectura(motor: Engine) -> None:
    """
    Crea (o actualiza) el rol de solo lectura con la contraseña del .env.
    La contraseña nunca queda escrita en el repositorio.
    """
    usuario = os.getenv("PG_BI_USER")
    clave = os.getenv("PG_BI_PASSWORD", "").replace("'", "''")
    if not usuario or not clave:
        raise EnvironmentError("Faltan PG_BI_USER o PG_BI_PASSWORD en el .env.")
    with motor.begin() as con:
        existe = con.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :u"), {"u": usuario}).scalar()
        accion = "ALTER" if existe else "CREATE"
        con.exec_driver_sql(f"{accion} ROLE \"{usuario}\" LOGIN PASSWORD '{clave}'")
    print(f"✅ Rol de solo lectura '{usuario}' {'actualizado' if existe else 'creado'}.")


# --------------------------------------------------------------------------
# Preparación de las tablas
# --------------------------------------------------------------------------
def preparar_tablas(pob: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Convierte la población (una fila por crédito) en las tablas del modelo."""
    pob = pob.sort_values("LoanOriginationDate").reset_index(drop=True)
    pob["credito_id"] = pob.index + 1

    # Deudores: una fila por MemberKey
    deudores = (pob.groupby("MemberKey")
                   .agg(creditos_en_cobranza=("credito_id", "size"),
                        primera_originacion=("LoanOriginationDate", "min"))
                   .reset_index()
                   .rename(columns={"MemberKey": "member_key"}))
    deudores.insert(0, "deudor_id", deudores.index + 1)
    deudores["primera_originacion"] = deudores["primera_originacion"].dt.date
    pob = pob.merge(deudores[["deudor_id", "member_key"]], left_on="MemberKey",
                    right_on="member_key", how="left")

    creditos = pob[["credito_id", "deudor_id"] + list(MAPEO_CREDITOS)].rename(columns=MAPEO_CREDITOS)
    for col in ["fecha_originacion", "fecha_cierre"]:
        creditos[col] = pd.to_datetime(creditos[col]).dt.date

    perfil = pob[["credito_id"] + list(MAPEO_PERFIL)].rename(columns=MAPEO_PERFIL)
    perfil["primera_linea_credito"] = pd.to_datetime(perfil["primera_linea_credito"],
                                                     errors="coerce").dt.date

    resultados = pob[["credito_id"] + list(MAPEO_RESULTADOS)].rename(columns=MAPEO_RESULTADOS)

    return {"deudores": deudores, "creditos": creditos,
            "perfil_solicitud": perfil, "resultados_recuperacion": resultados}


# --------------------------------------------------------------------------
# Carga y validación
# --------------------------------------------------------------------------
def cargar_tablas(motor: Engine, tablas: dict[str, pd.DataFrame]) -> None:
    """
    Inserta las tablas en orden padre -> hijo (respeta las llaves foráneas).
    Todo ocurre en UNA transacción: si algo falla, no queda una carga a medias.
    """
    with motor.begin() as con:
        for nombre in ORDEN_CARGA:
            df = tablas[nombre]
            df.to_sql(nombre, con, if_exists="append", index=False,
                      method="multi", chunksize=1000)
            print(f"  {nombre:25s} {len(df):>7,} filas")
    print("✅ Carga completa")


def validar_carga(motor: Engine, tablas: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Compara conteos y sumas de control entre pandas y PostgreSQL."""
    controles = [
        ("deudores", "COUNT(*)", len(tablas["deudores"])),
        ("creditos", "COUNT(*)", len(tablas["creditos"])),
        ("perfil_solicitud", "COUNT(*)", len(tablas["perfil_solicitud"])),
        ("resultados_recuperacion", "COUNT(*)", len(tablas["resultados_recuperacion"])),
        ("creditos", "SUM(monto_original)", tablas["creditos"]["monto_original"].sum()),
        ("resultados_recuperacion", "SUM(exposicion_castigo)",
         tablas["resultados_recuperacion"]["exposicion_castigo"].sum()),
        ("resultados_recuperacion", "SUM(recuperacion_total)",
         tablas["resultados_recuperacion"]["recuperacion_total"].sum()),
        ("resultados_recuperacion", "SUM(objetivo_a)",
         tablas["resultados_recuperacion"]["objetivo_a"].sum()),
    ]
    filas = []
    with motor.connect() as con:
        for tabla, expr, esperado in controles:
            obtenido = float(con.execute(text(f"SELECT {expr} FROM {tabla}")).scalar())
            filas.append({"tabla": tabla, "control": expr,
                          "pandas": round(float(esperado), 2), "postgres": round(obtenido, 2),
                          "ok": abs(float(esperado) - obtenido) < 1})
    resultado = pd.DataFrame(filas)
    print("✅ Validación superada" if resultado["ok"].all() else "❌ Hay diferencias: revisa la tabla")
    return resultado
