"""
Supuestos de negocio SIMULADOS (Fases 7 y 8).

Prosper no registra canales, costos ni resultados de gestiones de cobranza.
Todo lo de este archivo es un SUPUESTO EXPLÍCITO del equipo: se documenta, se guarda
en PostgreSQL (tabla canales) y en la Fase 8 se somete a análisis de sensibilidad.
Cambiar un número aquí y volver a ejecutar los notebooks 07 y 08 actualiza todo.
"""

# Costos en USD (el dataset es de EE. UU.).
# efectividad_supuesta = fracción de la recuperación esperada que se logra con ese canal,
# tomando la negociación con asesor (el canal más intensivo) como referencia = 1,0.
CANALES = [
    {"canal_id": 1, "nombre": "SMS", "costo_por_contacto_usd": 0.05, "efectividad_supuesta": 0.40,
     "fuente_supuesto": "Supuesto del equipo: SMS masivo; costo de referencia de proveedores de mensajería."},
    {"canal_id": 2, "nombre": "WhatsApp", "costo_por_contacto_usd": 0.10, "efectividad_supuesta": 0.55,
     "fuente_supuesto": "Supuesto del equipo: mensaje plantilla de WhatsApp Business; mayor tasa de lectura que SMS."},
    {"canal_id": 3, "nombre": "Llamada de asesor", "costo_por_contacto_usd": 3.00, "efectividad_supuesta": 0.80,
     "fuente_supuesto": "Supuesto del equipo: ~10 min de asesor + telefonía."},
    {"canal_id": 4, "nombre": "Negociación con asesor", "costo_por_contacto_usd": 15.00, "efectividad_supuesta": 1.00,
     "fuente_supuesto": "Supuesto del equipo: varias llamadas y formalización de acuerdo de pago."},
    {"canal_id": 5, "nombre": "Venta de cartera", "costo_por_contacto_usd": 0.00, "efectividad_supuesta": None,
     "fuente_supuesto": "Supuesto del equipo: se vende el crédito a un tercero; el precio se simula en la Fase 8."},
]

# Acción y canal según el tipo de segmento (P alta/baja × saldo alto/bajo)
ACCIONES = {
    ("alta", "bajo"): {"nombre": "Recordatorio automático", "canal": "WhatsApp",
                       "accion": "Mensaje automático con enlace de pago; SMS si no hay lectura en 48 h.",
                       "descripcion": "Alta probabilidad de pago y saldo bajo: un recordatorio barato basta."},
    ("alta", "alto"): {"nombre": "Negociación prioritaria", "canal": "Negociación con asesor",
                       "accion": "Asignar asesor senior; ofrecer acuerdo de pago o refinanciación.",
                       "descripcion": "Alta probabilidad y saldo alto: donde más dinero se recupera por contacto."},
    ("baja", "alto"): {"nombre": "Contacto selectivo", "canal": "Llamada de asesor",
                       "accion": "Una llamada de diagnóstico; escalar a negociación solo si hay disposición.",
                       "descripcion": "Baja probabilidad pero saldo alto: vale un contacto, no un esfuerzo intensivo."},
    ("baja", "bajo"): {"nombre": "Baja recuperación / venta de cartera", "canal": "Venta de cartera",
                       "accion": "No gestionar activamente; evaluar venta a un tercero.",
                       "descripcion": "Baja probabilidad y saldo bajo: gestionar cuesta más de lo que se espera recuperar."},
}

# Regla de negocio previa a K-Means: "First Payment Default" (FPD). Un crédito que cae en
# default en la primera cuota es una señal clásica de posible fraude en banca. En Prosper
# este grupo recupera casi todo (probable recompra/rescisión por la plataforma): no es
# "cobranza normal" y se gestiona aparte.
CUOTA_MAXIMA_FPD = 1
ACCION_FPD = {"nombre": "Default en primera cuota (revisión de fraude)", "canal": "Negociación con asesor",
              "accion": "Verificar identidad y documentos; escalar a fraude o recompra antes de cobrar.",
              "descripcion": "Cayó en default en la cuota 0-1: patrón típico de fraude (FPD); "
                             "en Prosper casi siempre se recupera, probablemente por recompra de la plataforma."}
