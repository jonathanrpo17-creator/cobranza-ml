"""
Diccionario de negocio de las 81 variables de Prosper.

Es la ÚNICA fuente de verdad sobre el rol de cada columna. La ingeniería de
variables (Fase 5) lee de aquí qué columnas puede usar como predictoras, para
que ninguna variable con fuga de datos entre al modelo por error.

Momento de predicción: el modelo se usa cuando el crédito ENTRA A COBRANZA.
Solo es válida la información conocida en ese momento (datos de la solicitud y
de la originación). Todo lo que se registra después es fuga de datos.

Roles:
  id           identificador; nunca es predictora
  fecha        fecha de un evento; se usa para ordenar en el tiempo o derivar variables
  filtro       define la población objetivo (no es predictora)
  predictora   conocida al originar el crédito; candidata a variable del modelo
  revisar      podría conocerse al entrar en mora; se decide en la Fase 5 con evidencia
  fuga         registrada después del desenlace; solo para objetivo/ROI o descartada
"""

DICCIONARIO = {
    # ---------------- Identificadores ----------------
    "ListingKey": ("id", "Llave única de la solicitud (listing) en Prosper."),
    "ListingNumber": ("id", "Número de la solicitud; equivalente numérico de ListingKey."),
    "LoanKey": ("id", "Llave única del crédito desembolsado."),
    "LoanNumber": ("id", "Número del crédito; equivalente numérico de LoanKey."),
    "MemberKey": ("id", "Llave del deudor. Un deudor puede tener varios créditos (base de la tabla deudores)."),
    "GroupKey": ("id", "Llave del grupo de prestatarios al que pertenecía el deudor; mayormente vacía."),

    # ---------------- Fechas ----------------
    "ListingCreationDate": ("fecha", "Fecha de creación de la solicitud."),
    "DateCreditPulled": ("fecha", "Fecha de consulta del reporte de crédito del deudor."),
    "LoanOriginationDate": ("fecha", "Fecha de desembolso. Eje de la partición temporal (entrenar con antiguos, validar con recientes)."),
    "LoanOriginationQuarter": ("fecha", "Trimestre de desembolso (texto, ej. 'Q3 2007'); útil para gráficas de cosecha."),

    # ---------------- Filtro de población ----------------
    "LoanStatus": ("filtro", "Estado actual del crédito. Chargedoff/Defaulted = población objetivo; Past Due = cartera en mora activa."),

    # ---------------- Fuga de datos ----------------
    "ClosedDate": ("fuga", "Fecha de cierre del crédito; ocurre después del desenlace. Solo para objetivo/ROI."),
    "LP_CustomerPayments": ("fuga", "Total pagado por el deudor durante toda la vida del crédito (incluye pagos posteriores a la mora)."),
    "LP_CustomerPrincipalPayments": ("fuga", "Total de capital pagado por el deudor durante toda la vida del crédito."),
    "LP_InterestandFees": ("fuga", "Total de intereses y cargos pagados por el deudor."),
    "LP_ServiceFees": ("fuga", "Comisiones de servicio acumuladas (valores negativos = cobros a inversionistas)."),
    "LP_CollectionFees": ("fuga", "Costos de cobranza acumulados; insumo para el ROI."),
    "LP_GrossPrincipalLoss": ("fuga", "Pérdida bruta de capital al castigar el crédito."),
    "LP_NetPrincipalLoss": ("fuga", "Pérdida neta de capital después de recuperaciones."),
    "LP_NonPrincipalRecoverypayments": ("fuga", "Recuperaciones posteriores al castigo que no son capital."),
    "LoanCurrentDaysDelinquent": ("fuga", "Días de mora a la fecha de extracción del dataset (2014); es una foto posterior al desenlace."),
    "LoanMonthsSinceOrigination": ("fuga", "Meses desde el desembolso hasta la extracción (2014); depende de la fecha de corte, no del deudor."),

    # ---------------- A revisar en la Fase 5 ----------------
    "LoanFirstDefaultedCycleNumber": ("revisar", "Cuota en la que el crédito cayó en default por primera vez. Se conoce al entrar en mora, pero hay que confirmar que esté disponible para toda la población."),

    # ---------------- Condiciones del crédito (predictoras) ----------------
    "Term": ("predictora", "Plazo del crédito en meses."),
    "LoanOriginalAmount": ("predictora", "Monto desembolsado (USD)."),
    "MonthlyLoanPayment": ("predictora", "Cuota mensual programada (USD)."),
    "BorrowerAPR": ("predictora", "Tasa anual efectiva para el deudor, incluyendo cargos."),
    "BorrowerRate": ("predictora", "Tasa de interés nominal del deudor."),
    "LenderYield": ("predictora", "Rendimiento para el inversionista (tasa menos comisión de servicio)."),
    "ListingCategory (numeric)": ("predictora", "Propósito del crédito, codificado (0 = no disponible; consolidación de deudas, negocio, etc.)."),
    "PercentFunded": ("predictora", "Porcentaje de la solicitud financiado por inversionistas."),
    "Investors": ("predictora", "Número de inversionistas que financiaron el crédito."),
    "Recommendations": ("predictora", "Número de recomendaciones recibidas en la solicitud."),
    "InvestmentFromFriendsCount": ("predictora", "Número de amigos que invirtieron en el crédito."),
    "InvestmentFromFriendsAmount": ("predictora", "Monto invertido por amigos (USD)."),

    # ---------------- Calificación de riesgo (dos épocas) ----------------
    "CreditGrade": ("predictora", "Calificación de Prosper de la época antigua (antes de 2009); vacía en la época reciente."),
    "ProsperRating (numeric)": ("predictora", "Calificación de Prosper de la época reciente (desde 2009), numérica 1-7."),
    "ProsperRating (Alpha)": ("predictora", "Misma calificación reciente en letras (AA a HR); redundante con la numérica."),
    "ProsperScore": ("predictora", "Puntaje de riesgo propio de Prosper (época reciente)."),
    "EstimatedEffectiveYield": ("predictora", "Rendimiento efectivo estimado por Prosper al originar (época reciente)."),
    "EstimatedLoss": ("predictora", "Pérdida estimada por Prosper al originar (época reciente)."),
    "EstimatedReturn": ("predictora", "Retorno estimado por Prosper al originar (época reciente)."),

    # ---------------- Perfil del deudor ----------------
    "BorrowerState": ("predictora", "Estado de residencia del deudor (EE. UU.)."),
    "Occupation": ("predictora", "Ocupación declarada."),
    "EmploymentStatus": ("predictora", "Situación laboral declarada."),
    "EmploymentStatusDuration": ("predictora", "Meses en la situación laboral actual."),
    "IsBorrowerHomeowner": ("predictora", "Indica si el deudor es propietario de vivienda."),
    "CurrentlyInGroup": ("predictora", "Indica si el deudor pertenecía a un grupo al solicitar."),
    "IncomeRange": ("predictora", "Rango de ingresos anuales declarado."),
    "IncomeVerifiable": ("predictora", "Indica si el deudor aportó soporte de ingresos."),
    "StatedMonthlyIncome": ("predictora", "Ingreso mensual declarado (USD)."),
    "DebtToIncomeRatio": ("predictora", "Relación deuda/ingreso al solicitar."),

    # ---------------- Historial en la central de riesgo ----------------
    "CreditScoreRangeLower": ("predictora", "Límite inferior del rango de puntaje de crédito del bureau."),
    "CreditScoreRangeUpper": ("predictora", "Límite superior del rango; redundante con el inferior (rango de 19 puntos)."),
    "FirstRecordedCreditLine": ("predictora", "Fecha de la primera línea de crédito; viene como texto y se convertirá en antigüedad crediticia."),
    "CurrentCreditLines": ("predictora", "Líneas de crédito vigentes."),
    "OpenCreditLines": ("predictora", "Líneas de crédito abiertas."),
    "TotalCreditLinespast7years": ("predictora", "Líneas de crédito en los últimos 7 años."),
    "OpenRevolvingAccounts": ("predictora", "Cuentas rotativas abiertas (tarjetas, cupos)."),
    "OpenRevolvingMonthlyPayment": ("predictora", "Pago mensual en cuentas rotativas (USD)."),
    "InquiriesLast6Months": ("predictora", "Consultas a la central en los últimos 6 meses."),
    "TotalInquiries": ("predictora", "Total de consultas a la central."),
    "CurrentDelinquencies": ("predictora", "Obligaciones en mora al momento de solicitar."),
    "AmountDelinquent": ("predictora", "Monto en mora al momento de solicitar (USD)."),
    "DelinquenciesLast7Years": ("predictora", "Moras en los últimos 7 años."),
    "PublicRecordsLast10Years": ("predictora", "Registros públicos negativos en 10 años (quiebras, embargos)."),
    "PublicRecordsLast12Months": ("predictora", "Registros públicos negativos en 12 meses."),
    "RevolvingCreditBalance": ("predictora", "Saldo en crédito rotativo (USD)."),
    "BankcardUtilization": ("predictora", "Porcentaje de uso del cupo de tarjetas."),
    "AvailableBankcardCredit": ("predictora", "Cupo disponible en tarjetas (USD)."),
    "TotalTrades": ("predictora", "Total de obligaciones registradas."),
    "TradesNeverDelinquent (percentage)": ("predictora", "Porcentaje de obligaciones que nunca han estado en mora."),
    "TradesOpenedLast6Months": ("predictora", "Obligaciones abiertas en los últimos 6 meses."),
    "ScorexChangeAtTimeOfListing": ("predictora", "Cambio del puntaje de crédito desde el último crédito con Prosper."),

    # ---------------- Historial previo con Prosper ----------------
    # Nulo = el deudor NO tenía créditos previos con Prosper (el nulo tiene significado).
    "TotalProsperLoans": ("predictora", "Créditos previos con Prosper (nulo = ninguno)."),
    "TotalProsperPaymentsBilled": ("predictora", "Cuotas facturadas en créditos previos con Prosper."),
    "OnTimeProsperPayments": ("predictora", "Cuotas pagadas a tiempo en créditos previos con Prosper."),
    "ProsperPaymentsLessThanOneMonthLate": ("predictora", "Cuotas pagadas con menos de un mes de atraso en créditos previos."),
    "ProsperPaymentsOneMonthPlusLate": ("predictora", "Cuotas pagadas con un mes o más de atraso en créditos previos."),
    "ProsperPrincipalBorrowed": ("predictora", "Capital total prestado en créditos previos con Prosper (USD)."),
    "ProsperPrincipalOutstanding": ("predictora", "Capital pendiente de créditos previos con Prosper al solicitar (USD)."),
}


def columnas_por_rol(rol: str) -> list[str]:
    """Devuelve las columnas que tienen un rol dado (ej. 'predictora', 'fuga')."""
    return [col for col, (r, _) in DICCIONARIO.items() if r == rol]
