# Guía del dashboard en Power BI Desktop

Esta guía arma el dashboard **conectado a PostgreSQL** con el usuario de solo lectura `lector_bi`, en 5 páginas. Calcula unas 2 horas la primera vez.

## 0. Requisitos

- **Power BI Desktop** (gratis): Microsoft Store → "Power BI Desktop" → Instalar.
- PostgreSQL encendido y los notebooks **04 a 09 ejecutados** en este computador.
- La contraseña de `lector_bi` (la que está en tu `.env` como `PG_BI_PASSWORD`).

## 1. Conectar a PostgreSQL

1. Abre Power BI Desktop → **Obtener datos** → **Más…** → **Base de datos PostgreSQL** → Conectar.
2. Servidor: `localhost:5432` · Base de datos: `cobranza` · Modo: **Importar** → Aceptar.
3. Credenciales: pestaña **Base de datos** · Usuario: `lector_bi` · Contraseña: la del `.env` → Conectar.
4. Si aparece un aviso de **cifrado/SSL**, acepta conectarte **sin cifrar**. La base es local y nunca sale de tu computador.
5. En el Navegador, marca:
   - `vw_cartera_cobranza`, `vw_resumen_cohortes`, `vw_roi_campanas`, `vw_roi_segmentos`
   - `segmentos`, `canales`

   Luego haz clic en **Cargar**.

> ¿Por qué `lector_bi` y no `postgres`? Por **mínimo privilegio**: el dashboard solo puede leer vistas. No ve las tablas con datos personales ni puede modificar nada. Las credenciales no quedan guardadas dentro del `.pbix`.

## 2. Cargar los resultados de la simulación (CSV)

**Obtener datos → Texto/CSV**, uno por uno, desde la carpeta `docs/` del proyecto:

| Archivo | Para qué |
|---|---|
| `roi_estrategias.csv` | Comparación de las 6 estrategias |
| `roi_curva_presupuesto.csv` | Curva sin modelo frente a con modelo |
| `roi_sensibilidad.csv` | Los 10 escenarios de supuestos |
| `metricas_deciles.csv` | Lift por decil |

⚠️ **Muy importante, por los decimales:** los CSV usan **punto** decimal, y Power BI en español espera **coma**. En cada CSV, haz clic en **Transformar datos**. Luego, en cada columna numérica, ve a: clic derecho → **Cambiar tipo** → **Usar configuración regional…** → Tipo de datos: *Número decimal* · Configuración regional: **Inglés (Estados Unidos)**. Si te saltas este paso, verás números como 37460 donde debería decir 0,3746.

## 3. Modelo de datos

En la vista **Modelo** (tercer ícono de la izquierda):
- Arrastra `vw_cartera_cobranza[segmento]` hasta `segmentos[nombre]`. La relación es **Varios a uno** y filtra en una sola dirección.

## 4. Medidas (DAX)

Crea una tabla para agrupar las medidas: **Inicio → Especificar datos** → nómbrala `Medidas` → Cargar. Luego, en esa tabla, ve a **Nueva medida** y crea cada una:

```DAX
Créditos = COUNTROWS ( vw_cartera_cobranza )
Exposición USD = SUM ( vw_cartera_cobranza[exposicion_castigo] )
Recuperado USD = SUM ( vw_cartera_cobranza[recuperacion_total] )
Tasa de recuperación = DIVIDE ( [Recuperado USD], [Exposición USD] )
% que recupera algo = AVERAGE ( vw_cartera_cobranza[recupero_algo] )
P media = AVERAGE ( vw_cartera_cobranza[prob_recuperar] )
Monto esperado USD = SUM ( vw_cartera_cobranza[monto_esperado] )
Valor esperado neto USD = SUM ( vw_cartera_cobranza[valor_esperado] )
% de créditos = DIVIDE ( [Créditos], CALCULATE ( [Créditos], ALL ( vw_cartera_cobranza[segmento] ) ) )
% de USD recuperados = DIVIDE ( [Recuperado USD], CALCULATE ( [Recuperado USD], ALL ( vw_cartera_cobranza[segmento] ) ) )
USD por crédito = DIVIDE ( [Recuperado USD], [Créditos] )
```

Formato: las medidas con "%" o "Tasa" van en **Porcentaje** con 1 decimal, y las de USD en **Moneda** sin decimales.

## 5. Las 5 páginas

Usa una paleta consistente en todo el dashboard: **rojo** = sin modelo, **verde** = con modelo, **gris** = referencia.

### Página 1 · Resumen ejecutivo: *"El problema"*
- **4 tarjetas** (filtra en el panel de filtros de la página `estado_credito`: Chargedoff y Defaulted, es decir, todo): `Créditos`, `Exposición USD`, `Recuperado USD`, `Tasa de recuperación`.
  - Valores esperados: 17.010 · USD 79,8 M · USD 5,1 M · 6,4 %.
- **Gráfico de líneas** con `vw_resumen_cohortes`: eje X `anio_cierre`, valores `pct_recupera_algo`. Muestra la caída por censura en 2013–2014.
- **Cuadro de texto:** *"Solo 1 de cada 5 créditos castigados recupera algo. Gestionar a todos igual desperdicia ~4 de cada 5 contactos."*

### Página 2 · Segmentos: *"¿A quién gestionar?"*
- **Filtro de página:** `conjunto` = validacion.
- **Barras agrupadas:** eje `segmento`, valores `% de créditos` y `% de USD recuperados`. Es el gráfico clave: el segmento de baja recuperación tiene el 29 % de los créditos y solo el 7 % de los USD.
- **Tabla:** `segmento`, `Créditos`, `P media`, `% que recupera algo`, `USD por crédito`, `segmentos[accion_sugerida]`, `segmentos[canal_sugerido]`.
- **Segmentación (slicer):** `segmento`.

### Página 3 · Priorización: *"La lista de trabajo de hoy"*
- **Filtro de página:** `conjunto` = inmadura (la cartera activa).
- **Tarjetas:** `Créditos`, `Monto esperado USD`, `Valor esperado neto USD`.
- **Tabla ordenada por `prioridad`** (ascendente): `prioridad`, `loan_key`, `segmento`, `prob_recuperar`, `monto_esperado`, `canal_sugerido`. Activa **Filtro de N superior** = 50 por `prioridad`.
- **Columnas** con `metricas_deciles.csv`: eje `decil`, valor `lift`. Agrega una línea constante en 1 desde el panel de análisis.

### Página 4 · ROI simulado: *"¿Cuánto vale?"*
- **Barras horizontales** con `roi_estrategias.csv`: eje = nombre de la estrategia (primera columna), valor `incremental_usd`.
- **Barras horizontales:** mismo eje, valor `usd_por_usd_invertido`.
- **Tabla** con `canales`: `nombre`, `costo_por_contacto_usd`, `efectividad_supuesta`, `fuente_supuesto`.
- **Cuadro de texto obligatorio:** *"Canales, costos y efectividades son SUPUESTOS SIMULADOS: Prosper no registra gestiones de cobranza."*

### Página 5 · Sin modelo vs. con modelo: *"¿Se sostiene?"*
- **Gráfico de líneas** con `roi_curva_presupuesto.csv`: eje `presupuesto_pct`, valores `hibrido_sin_modelo_incremental` (rojo) y `mezcla_con_modelo_incremental` (verde).
- **Tarjeta:** `ganancia_mezcla_vs_mejor_sin_modelo_pct` filtrada en `presupuesto_pct` = 30 → **+16,4 %**.
- **Barras agrupadas** con `roi_sensibilidad.csv`: eje `escenario`, valores `sin_modelo_neto_usd` (rojo) y `modelo_neto_usd` (verde).
- **Cuadro de texto:** *"Con el mismo presupuesto y los mismos canales, decidir a quién llamar con el modelo recupera 16 % más, y gana en los 10 escenarios de supuestos."*

## 6. Guardar y compartir (sin licencias Pro)

1. **Archivo → Guardar como** → `powerbi/dashboard_cobranza.pbix`.
2. **Archivo → Exportar → Exportar a PDF** → `powerbi/dashboard_cobranza.pdf`. Sirve para quien no tenga Power BI.
3. **Capturas** de cada página (`Win + Shift + S`) → `docs/figuras/pbi_1_resumen.png` … `pbi_5_comparacion.png`. Se usan en el README y en las diapositivas.
4. **Video de 2 a 3 minutos** recorriendo el dashboard y la aplicación: `Win + G` (Barra de juegos) → Grabar. Súbelo a YouTube como *no listado* o a Drive, y enlázalo en el README.

## 7. Actualizar los datos

Si vuelves a ejecutar los notebooks, en Power BI haz clic en **Inicio → Actualizar**. Los CSV se actualizan solos si conservan el mismo nombre y la misma ruta.

## Errores comunes

| Error | Solución |
|---|---|
| "No se pudo conectar" / "connection refused" | PostgreSQL está apagado: `services.msc` → *postgresql-x64-17* → Iniciar |
| "password authentication failed" | Revisa la contraseña de `lector_bi` en el `.env`. En Power BI: **Archivo → Opciones → Configuración de origen de datos → Editar permisos** |
| "permission denied for view" | Ejecuta de nuevo el notebook 09, que vuelve a otorgar los permisos |
| Los números de los CSV salen gigantes | Falta el paso de configuración regional de la sección 2 |
| No aparece `vw_entradas_modelo` o `vw_roi_*` | Ejecuta el notebook 09 |
