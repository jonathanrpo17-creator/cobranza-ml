"""
Aplicación de consulta — Optimización de cobranza (Fase 9).

Ejecutar desde la raíz del proyecto:
    streamlit run app/app.py

Se conecta a PostgreSQL con el usuario de SOLO LECTURA (lector_bi) y usa el modelo
guardado en models/. Toda la lógica está en src/servicio.py.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from sqlalchemy import text

from src.bd import obtener_motor
from src.config import RUTAS
from src.servicio import alertas, cargar_artefactos, evaluar, explicar, leer_entradas

st.set_page_config(page_title="Cobranza inteligente", page_icon="💼", layout="wide")


# --------------------------------------------------------------------------
# Recursos (se cargan una sola vez)
# --------------------------------------------------------------------------
@st.cache_resource
def recursos():
    return obtener_motor(rol="lector"), cargar_artefactos()


@st.cache_data(ttl=600)
def consultar(sql: str, **params) -> pd.DataFrame:
    with recursos()[0].connect() as con:
        df = pd.read_sql(text(sql), con, params=params)
    for c in df.columns:  # NUMERIC -> float
        if df[c].dtype == object and len(df[c].dropna()) and type(df[c].dropna().iloc[0]).__name__ == "Decimal":
            df[c] = df[c].astype(float)
    return df


try:
    motor, art = recursos()
    segmentos = consultar("SELECT segmento_id, nombre, accion_sugerida, canal_sugerido FROM segmentos").set_index("segmento_id")
except Exception as e:  # mensaje claro en lugar de un error técnico
    st.error("No se pudo iniciar la aplicación.")
    st.markdown(
        "Revisa que **PostgreSQL esté encendido**, que el `.env` tenga `PG_BI_USER` y `PG_BI_PASSWORD`, "
        "y que se hayan ejecutado los notebooks **06, 07, 08 y 09**.")
    st.code(str(e))
    st.stop()

CONJUNTOS = {"Cartera activa (en cobranza hoy)": "inmadura", "Validación (2010–2012)": "validacion"}

st.title("💼 Cobranza inteligente")
st.caption("Prioriza qué deudores contactar y por qué canal · Modelo LightGBM + segmentación K-Means · "
           "Datos: Prosper Loan (EE. UU.). Canales y costos son **simulados**.")

tab_deudor, tab_cartera, tab_resultados = st.tabs(["🔎 Consultar deudor", "📋 Cartera priorizada", "📈 Resultados del modelo"])

# --------------------------------------------------------------------------
# 1. Consultar un deudor
# --------------------------------------------------------------------------
with tab_deudor:
    col_a, col_b = st.columns([1, 2])
    with col_a:
        conjunto = CONJUNTOS[st.selectbox("Cartera", list(CONJUNTOS))]
        top = consultar("""SELECT credito_id, loan_key, prioridad, segmento FROM vw_cartera_cobranza
                           WHERE conjunto = :c ORDER BY prioridad LIMIT 200""", c=conjunto)
        opciones = {f"#{r.prioridad} · crédito {r.credito_id} · {r.segmento}": r.credito_id for r in top.itertuples()}
        elegido = st.selectbox("Deudor (ordenado por prioridad)", list(opciones))
        manual = st.number_input("…o escribe un credito_id", min_value=0, value=0, step=1)
        credito_id = int(manual) if manual else opciones[elegido]

    entradas = leer_entradas(motor, credito_id)
    if entradas.empty:
        st.warning(f"No existe el crédito {credito_id} en la cartera gestionable.")
        st.stop()

    fila = entradas.iloc[0]
    res = evaluar(entradas, art).iloc[0]
    seg = segmentos.loc[int(res["segmento_id"])]

    with col_b:
        st.subheader(f"Crédito {credito_id}")
        m1, m2, m3 = st.columns(3)
        m1.metric("Probabilidad de recuperar algo", f"{res['prob_recuperar']:.0%}")
        m2.metric("Saldo estimado al default", f"USD {res['saldo_estimado']:,.0f}")
        m3.metric("Monto esperado a recuperar", f"USD {res['monto_esperado']:,.0f}")
        st.success(f"**Segmento:** {seg['nombre']}  \n**Acción sugerida:** {seg['accion_sugerida']}  \n"
                   f"**Canal:** {seg['canal_sugerido']}")
        for msg in alertas(fila):
            st.warning(msg)

    st.markdown("#### ¿Por qué el modelo da esta probabilidad?")
    exp = explicar(entradas, art)
    fig, ax = plt.subplots(figsize=(8, 3.6))
    colores = ["#2E8B57" if v > 0 else "#C44E52" for v in exp["contribucion"]]
    ax.barh(exp["nombre"][::-1], exp["contribucion"][::-1], color=colores[::-1])
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel("Contribución (verde = sube la probabilidad · rojo = la baja)")
    plt.tight_layout()
    st.pyplot(fig)
    with st.expander("Ver valores de las variables"):
        st.dataframe(exp[["nombre", "valor", "contribucion"]].round(3), hide_index=True)

    with st.expander("🧪 ¿Qué pasaría si…? (simulación sobre este deudor)"):
        c1, c2, c3 = st.columns(3)
        nueva = entradas.copy()
        cuota_actual = int(fila["cuota_primer_default"]) if pd.notna(fila["cuota_primer_default"]) else 12
        nueva["cuota_primer_default"] = c1.slider("Cuota en la que cayó en default", 0, 44, cuota_actual)
        nueva["ingreso_mensual"] = c2.number_input("Ingreso mensual (USD)", 0.0, 100000.0,
                                                   float(fila["ingreso_mensual"] or 0), step=250.0)
        moras = int(fila["moras_7_anios"]) if pd.notna(fila["moras_7_anios"]) else 0
        nueva["moras_7_anios"] = c3.slider("Moras en los últimos 7 años", 0, 30, min(moras, 30))
        r2 = evaluar(nueva, art).iloc[0]
        st.metric("Nueva probabilidad", f"{r2['prob_recuperar']:.0%}",
                  delta=f"{(r2['prob_recuperar'] - res['prob_recuperar']) * 100:+.1f} pp")
        st.caption(f"Nuevo segmento: {segmentos.loc[int(r2['segmento_id']), 'nombre']}")

# --------------------------------------------------------------------------
# 2. Cartera priorizada
# --------------------------------------------------------------------------
with tab_cartera:
    conjunto2 = CONJUNTOS[st.selectbox("Cartera ", list(CONJUNTOS))]
    cartera = consultar("""SELECT prioridad, credito_id, loan_key, segmento, accion_sugerida, canal_sugerido,
                                  ROUND(prob_recuperar::numeric, 3) AS prob_recuperar,
                                  ROUND(monto_esperado::numeric, 0) AS monto_esperado_usd,
                                  ROUND(valor_esperado::numeric, 0) AS valor_esperado_neto_usd,
                                  calificacion, plazo_meses
                           FROM vw_cartera_cobranza WHERE conjunto = :c ORDER BY prioridad""", c=conjunto2)
    elegidos = st.multiselect("Segmentos", sorted(cartera["segmento"].dropna().unique()),
                              default=sorted(cartera["segmento"].dropna().unique()))
    n = st.slider("Mostrar los primeros", 10, len(cartera), min(100, len(cartera)))
    vista = cartera[cartera["segmento"].isin(elegidos)].head(n)

    k1, k2, k3 = st.columns(3)
    k1.metric("Créditos mostrados", f"{len(vista):,}")
    k2.metric("Monto esperado", f"USD {vista['monto_esperado_usd'].sum():,.0f}")
    k3.metric("Valor esperado neto (simulado)", f"USD {vista['valor_esperado_neto_usd'].sum():,.0f}")
    st.dataframe(vista, hide_index=True, width="stretch")
    st.download_button("⬇️ Descargar lista de gestión (CSV)", vista.to_csv(index=False).encode("utf-8-sig"),
                       file_name="lista_gestion_cobranza.csv", mime="text/csv")
    resumen = (cartera.groupby(["segmento", "canal_sugerido"])
               .agg(creditos=("credito_id", "size"), monto_esperado_usd=("monto_esperado_usd", "sum"))
               .sort_values("monto_esperado_usd", ascending=False))
    st.markdown("#### Resumen por segmento")
    st.dataframe(resumen, width="stretch")

# --------------------------------------------------------------------------
# 3. Resultados del modelo (validación)
# --------------------------------------------------------------------------
with tab_resultados:
    met = art["metricas"]
    va = met["validacion_A"]
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("AUC (validación)", f"{va['auc_roc']:.3f}")
    r2.metric("PR-AUC", f"{va['pr_auc']:.3f}", delta=f"azar {va['pr_auc_azar']:.3f}", delta_color="off")
    r3.metric("Lift decil 1", f"{met['lift_decil_1']:.2f}×")
    r4.metric("Brier", f"{va['brier']:.3f}", delta=f"tasa base {va['brier_tasa_base']:.3f}", delta_color="off")

    roi_csv = RUTAS["docs"] / "roi_estrategias.csv"
    if roi_csv.exists():
        st.markdown("#### ROI simulado con el mismo presupuesto (validación)")
        st.dataframe(pd.read_csv(roi_csv, index_col=0), width="stretch")
    for fig_nombre, titulo in [("08_curva_presupuesto.png", "Recuperación según presupuesto"),
                               ("06_ganancia_usd.png", "Curva de ganancia en dólares"),
                               ("08_sensibilidad.png", "Sensibilidad a los supuestos")]:
        ruta = RUTAS["figuras"] / fig_nombre
        if ruta.exists():
            st.markdown(f"#### {titulo}")
            st.image(str(ruta))
    st.caption("Canales, costos y efectividades son supuestos simulados (src/supuestos.py). "
               "Las métricas son sobre créditos cerrados en 2010–2012, que el modelo no vio al entrenar.")
