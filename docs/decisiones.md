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

## Fase 5 — Variables y partición

**D20. Las variables se leen desde PostgreSQL.** La base es la única fuente de verdad. `src/variables.py` transforma los datos y lo usan el entrenamiento y la aplicación, así que un crédito nuevo se procesa exactamente igual que los de entrenamiento.

**D21. Variables nuevas, todas calculables al entrar a cobranza:**
- **Calificación unificada y ordinal** (AA=7 … HR=1), que combina `CreditGrade` y `ProsperRating`.
- **Saldo contractual estimado al default.** Usa amortización francesa con monto, tasa, plazo y cuota del primer default. Es una *estimación* a partir del contrato; la pérdida real al castigo es fuga y no se usa.
- **Proporción del plazo pagada antes del default.**
- **Cuota sobre ingreso.**
- **Antigüedad crediticia.**
- **Indicador de crédito previo con Prosper.** Un valor nulo significa "no tenía" y se convierte en 0 más el indicador.
- **Situación laboral unificada entre épocas:** Full-time, Part-time y Employed pasan a "Empleado".

**D22. Tres controles automáticos contra la fuga y la dependencia de la época:**
1. **Lista negra.** El código falla si una variable es un identificador, un desenlace o un objetivo. Además, `tests/` contiene pruebas con pytest.
2. **Estabilidad entre épocas.** Se descartan las variables cuyo % de nulos difiere más de 20 pp entre entrenamiento y validación, y las categóricas cuya distancia de variación total supera 0,30.
3. **AUC univariado.** Se revisa a mano cualquier variable que, por sí sola, tenga un AUC mayor que 0,90.

**D23. Exclusiones por diseño:**
- Variables de una sola época: `prosper_score` y `Estimated*`.
- `rango_ingresos`, porque sus etiquetas cambian entre épocas.
- `plazo_meses`, porque no varía.
- `tasa_apr`, porque es redundante.
- `creditos_en_cobranza`, porque es fuga.
- Las fechas de calendario.

**D24. Deudores presentes en entrenamiento y validación.** Se marcan con `deudor_visto_en_entrenamiento`. Como el identificador no es una variable del modelo, no se excluyen. En la Fase 6 las métricas se reportan con y sin estos casos.

**D25. Resultados reales de los controles de la Fase 5:**
- **Candidatas:** 48 variables. **Finales:** 35 (33 numéricas y 2 categóricas: `estado_residencia` y `ocupacion`).
- **Bloque de 11 variables del bureau descartado por época.** En entrenamiento tienen 35,2 % de nulos y en validación 2,4 %, porque Prosper empezó a registrarlas alrededor de 2007. Son, entre otras: `uso_tarjetas`, `obligaciones_totales`, `pct_obligaciones_sin_mora`, `saldo_rotativo` y `lineas_credito_actuales`.
- **`proposito` descartado.** El código 0 ("no disponible") es el 71,1 % en entrenamiento y el 19,6 % en validación (distancia de variación total 0,515).
- **`situacion_laboral` descartada.** "Sin dato" es el 35,2 % frente al 2,4 % (distancia 0,328): es el mismo bloque de época.
- **Bajo vigilancia:** `estado_residencia` ("Sin dato": 17,6 % frente a 3,9 %) y `ocupacion` (9,5 % frente a 0,2 %). En la Fase 6 se revisa con SHAP si el modelo le da peso a "Sin dato".
- **AUC univariado máximo: 0,547** (`ingreso_mensual_log`). Ninguna variable es sospechosa de fuga, pero la señal individual es débil. Por eso el valor se mide con métricas de priorización: lift, ganancia acumulada y ROI.
- **Deudores repetidos entre entrenamiento y validación: 15** (0,5 % de la validación). El efecto es despreciable.
- **Cambio de distribución en el objetivo B.** La tasa media cuando hay recuperación es 20,8 % en entrenamiento y 37,6 % en validación.

## Fase 6 — Modelos

**D26. Protocolo de entrenamiento:**
- La validación (cierres de 2010 en adelante) **no se usa para ajustar nada**.
- La parada temprana de LightGBM y la calibración de Platt usan el 25 % más reciente del entrenamiento (bloque de control).
- El modelo A se elige con una regla fijada de antemano: el mayor AUC en toda la validación. Si dos candidatos quedan a menos de 0,005, gana el más simple.

**D27. Experimento con las variables del bureau.** Se compara LightGBM con 35 variables y todo el entrenamiento contra LightGBM con 46 variables, entrenado solo con los créditos que tienen datos del bureau. La comparación se hace sobre el mismo grupo de validación.

**D28. Monto esperado = P(A) × tasa esperada (B) × saldo contractual estimado al default.** El saldo real al castigo es fuga, por eso se usa la estimación según el contrato.

**D29. Resultados de la primera ejecución del notebook 06** (validación: 3.163 créditos cerrados entre 2010 y 2012):

| Modelo A | AUC | PR-AUC (azar 0,297) | Brier (tasa base 0,2087) |
|---|---|---|---|
| Logística (línea base) | 0,6334 | 0,5006 | 0,1911 |
| **LightGBM** | **0,6544** | **0,5229** | **0,1848** |

- **Lift del decil 1: 2,21.** En el 10 % mejor calificado recupera el 65,6 % de los créditos, frente a un promedio de 29,7 %. Ese decil concentra el 22 % de los créditos que recuperan y el 29 % de los USD.
- **Calibración:** el modelo subestima de forma sistemática. La probabilidad media es 0,259 y la tasa real es 0,297. Era lo esperado, porque la tasa base de validación es mayor (D19). No se recalibra con la validación, porque eso sería usarla para ajustar. El ROI resultante será conservador.
- **Sin los 15 deudores repetidos, el AUC es 0,6543.** No hay efecto.

**D30. El experimento del bureau se descarta con evidencia.** Con las 11 variables del bureau y 5.551 créditos de entrenamiento, el AUC es 0,6425. Con las 35 variables y 8.543 créditos es 0,6544. Tener más historia pesa más que tener más variables.

**D31. Etapa B débil y declarada como limitación.** El MAE es 0,342 frente a 0,398 del promedio, pero el R² es −0,002. El modelo no explica la variación de la tasa dentro de la validación. Es probable que la tasa dependa de las gestiones de cobranza, que Prosper no registra. En el notebook 06 (sección 10) se mide el aporte real de la etapa B comparando P(A) × saldo con P(A) × B × saldo.

**D32. Ganancia en USD** (primera ejecución, % de los USD recuperados capturados):

| Orden | Top 10 % | Top 20 % | Top 50 % |
|---|---|---|---|
| Azar | 10,6 % | 22,6 % | 49,7 % |
| Por probabilidad (A) | 29,3 % | 38,0 % | 65,0 % |
| Por monto esperado | 38,6 % | 49,1 % | 79,0 % |

Contactando el 20 % superior según el monto esperado se captura **2,2 veces** lo que se lograría al azar. Parte de esto viene del saldo, porque una deuda más grande permite recuperar más dólares. Es legítimo, ya que el saldo se conoce al entrar a cobranza, y se cuantifica en D31.

**D33. Regla D25 activada: salen `estado_residencia` y `ocupacion`.**
- SHAP ubicó a `estado_residencia` como la 2.ª variable más importante, y su categoría "Sin dato" tiene un SHAP medio de +0,087 frente a +0,003 del resto. "Sin dato" es el 17,6 % del entrenamiento y el 3,9 % de la validación: el modelo estaba leyendo la época.
- `ocupacion` (5.º lugar) tiene el mismo patrón y alta cardinalidad (67 categorías).
- Se excluyen **por principio, no por su AUC**. El notebook 06 (sección 4b) reporta el costo de la decisión.
- Las variables más importantes que se conservan tienen sentido de negocio: `cuota_primer_default` (1.ª), `pct_saldo_pendiente_estimado`, `moras_7_anios`, `lineas_credito_7_anios` e `ingreso_mensual_log`.

**D34. Modelo A oficial: LightGBM con 33 variables numéricas** (sin variables de época):
- AUC 0,6464, frente a 0,6225 de la regresión logística.
- PR-AUC 0,5144, cuando el azar daría 0,297.
- Brier 0,1859, frente a 0,2087 de la tasa base.
- **Lift del decil 1: 2,18.** En ese decil recupera el 64,7 % de los créditos, frente al 29,7 % promedio.
- La calibración de Platt mejora el Brier de 0,1888 a 0,1859.

El costo de sacar `estado_residencia` y `ocupacion` fue de 0,008 de AUC (0,6544 → 0,6464). En cambio, la captura de USD en el top 20 % **subió** de 38,0 % a 39,6 %. El modelo es más robusto y no pierde valor para el negocio.

**D35. SHAP sin señales de época.** Las cinco variables más importantes son:
1. `cuota_primer_default`
2. `moras_7_anios`
3. `lineas_credito_7_anios`
4. `ingreso_mensual_log`
5. `pct_saldo_pendiente_estimado`

Todas son información del deudor o del comportamiento de pago, y tienen sentido de negocio.

**D36. La etapa B no aporta a la priorización y se reemplaza por una tasa constante.**

| Orden (validación) | Top 10 % | Top 20 % | Top 30 % | Top 50 % |
|---|---|---|---|---|
| Azar | 10,6 % | 22,6 % | 34,5 % | 49,7 % |
| P(A) | 29,4 % | 39,6 % | 50,4 % | 64,5 % |
| **P(A) × saldo** | 35,8 % | **52,0 %** | **62,5 %** | **80,1 %** |
| P(A) × B × saldo | 36,8 % | 50,7 % | 59,9 % | 78,4 % |

Agregar la etapa B empeora la captura en el top 20–50 %, y su R² es aproximadamente 0 (D31). Por la regla de simplicidad:
- **E[monto] = P(A) × tasa media de entrenamiento × saldo estimado.**
- El orden de la cartera equivale al de P(A) × saldo.
- La tasa media de entrenamiento se usa para el nivel del ROI, y es conservadora porque la de validación es mayor.
- El LightGBM de la etapa B queda documentado como experimento y como limitación: la tasa depende de gestiones que no están en los datos.

**Resultado de negocio:** contactando el 20 % superior de la cartera se captura el **52 %** de los dólares recuperados, **2,3 veces** lo que se lograría al azar.

## Fase 7 — Valor esperado y segmentación

**D37. Valor esperado.**
- **Bruto** = P(A) × tasa media de recuperación de entrenamiento (cuando A=1) × saldo estimado al default.
- **Neto** = bruto × efectividad del canal − costo del canal.

Los costos y efectividades de los canales son **supuestos simulados** y explícitos (`src/supuestos.py`, tabla `canales`). En la Fase 8 se someten a un análisis de sensibilidad.

**D38. Segmentación con K-Means.**
- Variables: P(recuperar) y log(saldo), estandarizadas.
- Se ajusta con la **validación**, donde las predicciones son fuera de muestra, y luego se aplica a toda la cartera.
- k se elige por la mejor silueta entre 3 y 6, un rango con sentido operativo.
- Cada segmento se nombra con una regla transparente: su centro se compara con las medianas de P y de saldo.

| | Saldo bajo | Saldo alto |
|---|---|---|
| **P alta** | Recordatorio automático (WhatsApp) | Negociación prioritaria (asesor) |
| **P baja** | Baja recuperación / venta de cartera | Contacto selectivo (llamada) |

**D39. Las predicciones se guardan en PostgreSQL** (tabla `predicciones`, versión `lgbm_A_v1`, vigente). Power BI y la aplicación las leen a través de `vw_cartera_cobranza` con el rol de solo lectura. En el entrenamiento, la probabilidad es dentro de muestra, así que las conclusiones se sacan con la validación y la cartera inmadura.

**D40. Corrección del saldo estimado.** La primera ejecución de la Fase 7 mostró **495 créditos de validación (15,6 %) con saldo estimado igual a 0**, que en realidad recuperaron USD 66.307. La causa: el cálculo suponía que el deudor había pagado todas las cuotas hasta la del primer default, así que un crédito que caía en default cerca o después del vencimiento quedaba "sin deuda". La función única `saldo_al_default()` corrige esto:
- **Cuotas pagadas = cuota del primer default − 4.** Es un supuesto: el default se declara tras unos 120 días sin pago.
- **Piso = 4 cuotas impagas,** sin superar el monto original.

Se vuelven a ejecutar los notebooks 05, 06 y 07, y las métricas finales son las de esa nueva ejecución.

**D41. Regla de segmentación ajustada.** En la primera ejecución, la silueta eligió k=3 (0,77) porque separaba dos grupos extremos: el de saldo 0 (un error) y uno pequeño con P ≈ 0,96. El 80 % de la cartera quedó en un solo grupo y dos segmentos recibieron el mismo nombre. Nueva regla:
- Variables: logit(P) y log(saldo).
- k entre 4 y 6, porque hay 4 acciones de cobranza.
- Ningún segmento puede tener menos del 3 % de la cartera.
- Entre los k que cumplen, gana la mejor silueta.

**D42. Grupo de probabilidad muy alta.** En la primera ejecución, 139 créditos de validación (4,4 %) tenían P media de 0,956 y **realmente** recuperó el 97,1 % de ellos: un USD 1.866 por crédito, que suman el 21,9 % de los USD recuperados. Se perfila en el notebook 07 (sección 6b) para explicar qué patrón detecta el modelo.

**D43. Segunda corrección del saldo.** Después de D40 seguían 20 créditos de validación con saldo cercano a 0, porque su `cuota_mensual` reportada es 0. Ahora el piso se calcula con la **cuota contractual** (a partir del monto, la tasa y el plazo), no con la cuota reportada.

**D44. Segmento "Default en primera cuota" (FPD) definido por regla de negocio.** El grupo de probabilidad muy alta (139 créditos, P ≈ 0,955, recuperación real 97,1 %) cayó en default en la **cuota 0 o 1**: 124 créditos en la cuota 1 y 10 en la cuota 0. El *First Payment Default* es una señal clásica de fraude en banca. En Prosper ese grupo recupera casi todo, y la **hipótesis** es que la plataforma recompra o rescinde los créditos con fraude confirmado. Los datos no permiten verificarlo.

En consecuencia:
1. El grupo FPD forma el **segmento 1** por regla y K-Means segmenta el resto.
2. Su acción es la **revisión de fraude antes de cobrar**.
3. En el notebook 07 (sección 6c) se reporta la captura de USD **con y sin FPD**, porque si ese valor viene de recompras no sería trasladable a la cobranza de un banco.

**D45. Notebook 06 con el saldo corregido** (validación, 3.163 créditos):
- **LightGBM:** AUC 0,6438.
- **Regresión logística:** AUC 0,6365. Su PR-AUC (0,5397) y su captura en el top 20 % (43,2 %) son mayores, pero la regla de elección (AUC, con un margen de 0,005) mantiene LightGBM. Se reporta con transparencia.
- **Lift del decil 1:** 2,24.
- **Captura de USD en el top 20 % ordenando por P × saldo:** 53,8 %, frente a 22,6 % al azar.

**D46. Resultados finales de las Fases 6 y 7** (validación con el saldo corregido, 3.163 créditos):

*Modelo A*
- **LightGBM** (179 árboles): AUC 0,6463, PR-AUC 0,5171 y Brier 0,1858, frente a 0,2087 de la tasa base.
- **Regresión logística:** AUC 0,6306.

*Captura de USD ordenando por P × saldo* (la etapa B no se usa, D36)

| Contactando | Top 10 % | Top 20 % | Top 30 % | Top 50 % |
|---|---|---|---|---|
| Azar | 10,6 % | 22,6 % | 34,5 % | 49,7 % |
| **P(A) × saldo** | **37,5 %** | **52,9 %** | **65,1 %** | **81,9 %** |

*Sensibilidad sin FPD*
- Captura en el top 20 %: **45,8 %**, frente a 18,6 % al azar, es decir **2,5 veces más**.
- **El valor del modelo no depende del grupo FPD.**

*Nivel*
- USD esperados: 904.132. USD reales: 1.182.216.
- El modelo es conservador: subestima un 23,5 %.

*Segmentación* (k=4 sobre la cartera sin FPD; k=3 tenía mejor silueta, pero quedaba fuera del rango operativo; k=5 y k=6 generaban segmentos del 0,2 %)

| Segmento | % créditos | Recupera (real) | USD real / crédito | % USD real |
|---|---|---|---|---|
| 1. Default en primera cuota (fraude) | 4,2 % | 97,8 % | 1.885 | 21,4 % |
| 2. Contacto selectivo | 27,0 % | 22,3 % | 443 | 32,1 % |
| 3. Negociación prioritaria | 26,8 % | 27,6 % | 410 | 29,4 % |
| 4. Recordatorio automático | 12,8 % | 40,8 % | 288 | 9,9 % |
| 5. Baja recuperación / venta | 29,2 % | 23,6 % | 94 | 7,3 % |

**Lectura de negocio:**
- El 29 % de la cartera (segmento 5) aporta solo el 7 % de los dólares.
- El segmento 4 es el que más recupera en frecuencia (40,8 %), pero con saldos bajos. Un recordatorio barato es suficiente para él.
- Los segmentos 2 y 3 concentran el 61 % de los USD.
- En la Fase 8 se optimiza la asignación de canales a cada segmento con los costos simulados.

**Cartera activa inmadura** (5.196 créditos para priorizar en la aplicación): el valor esperado neto suma unos USD 1,77 millones, según los supuestos simulados.

## Fase 8 — Simulación de campaña y ROI

**D47. Supuestos de simulación** (`src/supuestos.py` y `src/simulacion.py`). Todos son simulados:
- La recuperación real de Prosper es lo que logra la gestión más intensiva (negociación, efectividad 1,0).
- **Contactado por el canal *c*:** recupera lo real × efectividad(*c*).
- **No contactado:** recupera lo real × 10 % (pago espontáneo).
- **Venta de cartera:** ingresa el 4 % del saldo estimado.
- **KPI:** USD recuperados por encima de no gestionar, por cada USD invertido.

**D48. Protocolo.**
- Las estrategias se comparan en la **validación**, con el **mismo presupuesto** (30 % del costo de llamar a todos).
- El canal de cada segmento se **optimiza con el entrenamiento** para ese presupuesto: búsqueda por coordenadas sobre el beneficio neto simulado.
- Dentro de la campaña, el orden de gestión es el valor incremental esperado **por USD**, según el modelo (criterio voraz de la mochila).

**D49. Una línea base sin modelo que también usa canales baratos.** Se agregó "WhatsApp a todos + llamadas al azar" para separar el valor del **modelo** del valor de **suponer canales digitales baratos**. En la sensibilidad, el modelo se compara contra la **mejor** estrategia sin modelo.

**D50. Sensibilidad.** Se evalúan 10 escenarios: efectividad ±50 %, costos ×0,5 y ×2, pago espontáneo de 0 % y 20 %, precio de venta de 2 % y 8 %, y un escenario pesimista combinado. En cada uno se vuelve a optimizar el canal con el entrenamiento.

**D51. Resultados de la primera ejecución del notebook 08** (validación, presupuesto de USD 2.844, el 30 % de llamar a todos):

| Estrategia | USD incrementales | USD por USD invertido |
|---|---|---|
| Sin modelo: llamadas al azar | 246.570 | 86,7 |
| **Con modelo: llamadas priorizadas por P × saldo** | **538.682** | **189,4** |
| Sin modelo: WhatsApp a todos + llamadas al azar | 613.311 | 215,6 |
| Con modelo: canal optimizado por segmento | 608.516 | 213,9 |

**Hallazgos:**
1. **El valor puro de la priorización es grande.** Con el mismo canal y el mismo presupuesto, el modelo recupera **2,2 veces más** que al azar (538.682 frente a 246.570).
2. **Un canal casi gratuito reduce el valor de priorizar.** Si se supone que WhatsApp cuesta USD 0,10 y tiene 55 % de efectividad, contactar a todos cuesta muy poco y queda poco que priorizar. El modelo aporta más cuando contactar es caro o poco efectivo: en los escenarios "efectividad −50 %" (+48 %) y "pesimista combinado" (+96 %) el modelo gana con claridad.
3. **La optimización de canal por segmento falló por el cambio entre periodos.** Con el entrenamiento, que tiene tasas de recuperación menores (D19), el optimizador decidió **vender** el segmento "Contacto selectivo", que en la validación aporta el 32 % de los USD. Con presupuesto completo, esa estrategia queda 12 % por debajo de llamar a todos.
   - **Lección:** las decisiones irreversibles, como la venta de cartera, no deben automatizarse con datos de otro periodo. Requieren revisión humana.
   - Se documenta como **riesgo**.

**D52. Comparación corregida: "WhatsApp a todos + llamadas priorizadas por el modelo".** La comparación justa frente a la estrategia híbrida sin modelo usa la **misma mezcla de canales y el mismo costo**. La única diferencia es *a quién* se llama, así que mide exactamente el valor del modelo. Se agregó después de ver los resultados del punto D51 y se declara así. Corresponde al diseño que debió hacerse desde el inicio para aislar el efecto del modelo. La estrategia por segmento se mantiene en el reporte.

**D53. Resultado final del ROI.** Comparación justa: misma mezcla de canales y mismo costo, cambiando solo a quién se llama.

| Presupuesto (% de llamar a todos) | Sin modelo (mejor) | **Con modelo** | Ganancia |
|---|---|---|---|
| 5 % (USD 474) | 537.324 | 574.836 | +7,0 % |
| 10 % (USD 949) | 551.200 | 623.797 | +13,2 % |
| 20 % (USD 1.898) | 582.356 | 677.680 | +16,4 % |
| **30 % (USD 2.847)** | **613.307** | **713.833** | **+16,4 %** |
| 50 % (USD 4.744) | 676.510 | 770.924 | +14,0 % |
| 75 % (USD 7.117) | 750.763 | 807.224 | +7,5 % |
| 100 % (USD 9.489) | 827.551 | 827.551 | 0 % (todos son contactados) |

Cifras en USD incrementales (por encima de no gestionar), sobre la validación.

- **Con el 30 % del presupuesto, el modelo recupera USD 100.526 más** que la mejor estrategia sin modelo. Son unos **251 USD por USD invertido**, frente a 216.
- **Con solo el 30 % del presupuesto, el modelo logra el 86 % de lo que se recuperaría llamando a todos** (713.833 / 827.551), y gasta el 70 % menos.
- La ganancia es máxima con presupuestos intermedios (20 % a 50 %), que es la situación real de un área de cobranza. Con el presupuesto completo la ventaja es cero, porque no queda nada que priorizar.
- **El modelo gana en los 10 escenarios de sensibilidad** frente a la mejor estrategia sin modelo. El detalle por escenario está en `docs/roi_sensibilidad.csv`.

**Mensaje para la sustentación:** *"Con el mismo presupuesto y los mismos canales, decidir a quién llamar con el modelo recupera un 16 % más. Esa ventaja se mantiene en los 10 escenarios de supuestos que probamos."*
