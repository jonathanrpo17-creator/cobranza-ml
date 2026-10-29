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

**D10. Censura y ventana de maduración de 24 meses.** La recuperación cae en los créditos cerrados recientemente: el % que recupera algo pasa de 32,6 % en 2010 a 13,2 % en 2013 y 5,6 % en 2014. Esos créditos no han tenido tiempo de mostrar sus recuperaciones.

La curva de maduración, con fecha de corte en marzo de 2014, sube con el tiempo de observación: 7,1 % (0–6 meses), 12,8 % (6–12), 20,4 % (12–18) y 21,5 % (24–30). Pasados los 48 meses vuelve a bajar, pero eso refleja las cosechas antiguas de 2006–2009, no la maduración.

Sensibilidad (créditos para modelar / % que recupera en ellos):

| Ventana | Créditos | % A=1 |
|---|---|---|
| 12 meses | 13.932 | 24,3 % |
| 18 meses | 12.543 | 24,7 % |
| **24 meses** | **11.706** | **25,2 %** |
| 30 meses | 11.078 | 25,4 % |
| 36 meses | 10.610 | 25,3 % |

A partir de 24 meses la tasa base se estabiliza en 25,2–25,4 %. Alargar la ventana a 36 meses descarta 1.096 créditos sin cambiar la tasa. **Decisión: 24 meses.**

Resultado:
- **11.706 créditos para modelar.**
- **5.196 créditos inmaduros con exposición** se usan como cartera a priorizar en la aplicación.
- 108 créditos sin exposición se excluyen.

**D11. `LoanFirstDefaultedCycleNumber` pasa a ser predictora.** Indica en qué cuota cayó el crédito en default y está disponible en el 99,3 % de la población (mediana: cuota 14). Se conoce al entrar a cobranza.

**D12. Señal univariada débil en las variables de originación** (medida sobre créditos maduros). Por calificación, el % que recupera va de 20,9 % (HR) a 27,6 % (C); por monto, de 23,5 % a 27,1 %. **Expectativa realista:** el valor del modelo dependerá de combinar varias variables y del comportamiento de pago antes de la mora, no de una sola variable estrella.

**D13. `Term` sin variación en la población de modelado.** El 99,8 % de los créditos maduros es a 36 meses: 11.685 de 11.706. Los plazos de 12 y 60 meses empezaron alrededor de 2010–2011 y casi todos están inmaduros. Por eso `Term` no aporta información al modelo. **Limitación:** aplicar el modelo a créditos de 60 meses es extrapolar, y se debe advertir en la aplicación.

**D14. Categorías que dependen de la época.** En `EmploymentStatus`, "Full-time" (26,6 %) frente a "Employed" (13,2 %) son la misma realidad con etiquetas de distintas épocas de Prosper. Lo mismo pasa con "Not displayed" en `IncomeRange`. En la Fase 5 se unifican estas categorías, para que el modelo no aprenda el año en lugar del deudor.

**D15. Partición temporal propuesta** (por año de cierre, entre créditos maduros):
- Entrenamiento: cierres de 2006 a 2009, 8.543 créditos (73 %).
- Validación: cierres de 2010 a 2012, 3.163 créditos (27 %).

Se confirma en la Fase 5.

## Fase 4 — Base de datos

**D16. PostgreSQL local con modelo relacional de 9 tablas y 2 vistas.** El diseño y su justificación completa están en `docs/modelo_er.md`. Puntos clave:
- `deudores` 1:N `creditos`.
- `perfil_solicitud` y `resultados_recuperacion` en relación 1:1 con `creditos`. El desenlace con fuga queda aislado.
- `predicciones` admite varias versiones del modelo.
- Canales y campañas simulados, con sus supuestos trazables en JSONB.

**D17. La calidad se garantiza dentro de la base.** Hay llaves foráneas, `UNIQUE` y `CHECK`. El notebook 04 prueba que se rechazan datos inválidos y valida la carga comparando conteos y sumas entre pandas y PostgreSQL.

**D18. Mínimo privilegio.** Power BI y la aplicación usan el rol `lector_bi`, que solo lee vistas y catálogos. Las contraseñas viven en `.env`, y la conexión se arma con `URL.create` para soportar caracteres especiales.

**D19. Etiqueta de conjunto en la base.** Valores: `entrenamiento` (cierres 2006–2009), `validacion` (2010 en adelante), `inmadura` y `excluida`. El año de corte es el parámetro `ANIO_INICIO_VALIDACION` y se confirma en la Fase 5.
