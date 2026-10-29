# Registro de decisiones del proyecto

Cada decisión técnica queda aquí con la evidencia que la respalda. Este registro alimenta el documento de sustentación y las respuestas a las preguntas del jurado.

---

## Fase 2 — Datos y calidad

**D1. Dataset verificado:** 113.937 filas × 81 columnas, 0 filas duplicadas exactas, 0 columnas vacías o constantes, 13 columnas con más del 50 % de nulos.

**D2. Lectura de fechas con `format="mixed"`.** En el CSV conviven fechas con y sin fracciones de segundo. Sin esta opción, `DateCreditPulled` aparecía con 74,71 % de nulos y fecha máxima en 2008. Con la corrección queda en 0 % y llega hasta 2014. Además, `cargar_crudo()` ahora reporta cualquier fecha que no se pueda convertir.

**D3. Momento de predicción = entrada a cobranza.** Solo se usa información conocida en ese momento. Con esta regla se identificaron 11 columnas con fuga: las 9 de la regla inicial más `LoanCurrentDaysDelinquent` y `LoanMonthsSinceOrigination`, ambas medidas a la fecha de extracción de 2014.

**D4. Diccionario de negocio como única fuente de verdad** (`src/diccionario.py`). La Fase 5 lee de ahí qué columnas son predictoras.

## Fase 3 — Población y variables objetivo

**D5. Duplicados.** Hay 871 filas repetidas de `LoanKey`, que solo difieren en `ProsperScore` (827 grupos). Regla conservadora: conservar el puntaje más bajo, es decir, el de mayor riesgo. Ninguna de estas filas pertenece a la población objetivo. Resultado: 113.066 créditos únicos.

**D6. Población objetivo:** 17.010 créditos (11.992 Chargedoff y 5.018 Defaulted), con una exposición total de USD 79,8 millones.

**D7. Variables objetivo** (modelo de dos etapas, tipo *hurdle*, análogo a la estimación de LGD):
- Exposición = `LP_GrossPrincipalLoss`.
- Recuperación = (`LP_GrossPrincipalLoss` − `LP_NetPrincipalLoss`, mínimo 0) + `LP_NonPrincipalRecoverypayments`.
- **A** = 1 si la recuperación es ≥ USD 1.
- **B** = recuperación ÷ exposición, acotada a [0, 1].

Ajustes por los chequeos de consistencia:
- En el 11,60 % de los créditos la pérdida neta supera a la bruta. Se trata como recuperación de capital igual a 0.
- En el 3,70 % la recuperación supera la exposición (9,65 % en Defaulted), porque se suman recuperaciones que no son capital. La tasa se acota a 100 %.
- El 0,63 % no tiene exposición (pérdida bruta ≤ 0). Se excluye del modelado.

**D8. Línea base de negocio (sin modelo):**
- Solo el **21,65 %** de los créditos castigados recupera algo.
- Se recuperaron **USD 5,10 millones de USD 79,8 millones (6,40 %)**.
- Cuando hay recuperación, la tasa mediana es 18,7 %. La distribución es bimodal: p25 = 4,1 %, p75 = 73 %.

**Implicación:** contactar a todos los deudores con la misma intensidad desperdicia esfuerzo en aproximadamente 4 de cada 5 casos.

**D9. `LoanStatus` nunca es predictora.** La diferencia entre Chargedoff y Defaulted es enorme: la tasa mediana cuando hay recuperación es 10,8 % frente a 70,1 %. Pero el estado es el desenlace final, no se conoce al entrar a cobranza, y usarlo sería fuga de datos.

**D10. Censura y ventana de maduración.** La recuperación cae en los créditos cerrados recientemente: el % que recupera algo pasa de 32,6 % en 2010 a 13,2 % en 2013 y 5,6 % en 2014. Esos créditos no han tenido tiempo de mostrar sus recuperaciones. Por eso:
- Solo los créditos con al menos 24 meses de observación después del cierre se usan para entrenar y validar.
- Los créditos inmaduros quedan como cartera para demostrar la priorización en la aplicación.
- La ventana se valida con la curva de maduración (notebook 03, sección 8b) y es un parámetro ajustable (`VENTANA_MADURACION_MESES`).

**D11. `LoanFirstDefaultedCycleNumber` pasa a ser predictora.** Indica en qué cuota cayó el crédito en default y está disponible en el 99,3 % de la población (mediana: cuota 14). Se conoce al entrar a cobranza.

**D12. Señal univariada débil en las variables de originación.** La tasa de recuperación por calificación varía apenas entre 18,5 % y 24,7 %. El plazo de 60 meses muestra 9,8 %, pero ese plazo solo existe desde 2010, así que el dato está confundido con la censura. **Expectativa realista:** el valor del modelo dependerá de combinar varias variables y del comportamiento de pago antes de la mora, no de una sola variable estrella.
