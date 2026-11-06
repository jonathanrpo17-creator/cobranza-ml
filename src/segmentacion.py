"""
Valor esperado y segmentación con K-Means (Fase 7).

Valor esperado bruto = P(recuperar) × tasa media de recuperación (entrenamiento) × saldo estimado
Valor esperado neto  = bruto × efectividad del canal − costo del canal        (supuestos simulados)

K-Means agrupa los créditos según logit(P(recuperar)) y el saldo (log). Cada grupo recibe un
nombre y una acción con una regla transparente: su P media y su saldo medio comparados
con las medianas de la cartera.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from src.config import SEMILLA
from src.supuestos import ACCION_FPD, ACCIONES, CANALES, CUOTA_MAXIMA_FPD

VARIABLES_SEGMENTO = ["logit_p", "saldo_log"]
TAMANO_MINIMO = 0.03  # ningún segmento operativo con menos del 3 % de la cartera


def preparar(datos: pd.DataFrame) -> pd.DataFrame:
    """logit(P) separa mejor las probabilidades bajas, que son la mayoría de la cartera."""
    datos = datos.copy()
    p = datos["prob_recuperar"].clip(1e-4, 1 - 1e-4)
    datos["logit_p"] = np.log(p / (1 - p))
    return datos


def es_fpd(datos: pd.DataFrame) -> pd.Series:
    """True si el crédito cayó en default en la primera cuota (regla de negocio)."""
    return datos["cuota_primer_default"].le(CUOTA_MAXIMA_FPD).fillna(False)


def evaluar_k(datos: pd.DataFrame, ks=range(2, 9)) -> pd.DataFrame:
    """Inercia (método del codo) y silueta para cada k."""
    datos = datos[~es_fpd(datos)]
    X = StandardScaler().fit_transform(preparar(datos)[VARIABLES_SEGMENTO])
    filas = []
    for k in ks:
        km = KMeans(n_clusters=k, n_init=20, random_state=SEMILLA).fit(X)
        filas.append({"k": k, "inercia": round(km.inertia_, 1),
                      "segmento_mas_pequeno_pct": round(np.bincount(km.labels_).min() / len(X) * 100, 1),
                      "silueta": round(silhouette_score(X, km.labels_, sample_size=min(5000, len(X)),
                                                        random_state=SEMILLA), 4)})
    return pd.DataFrame(filas).set_index("k")


class Segmentador:
    """Escalador + K-Means + reglas de nombre. Se ajusta una vez y se aplica a toda la cartera."""

    def __init__(self, k: int):
        self.k = k

    def fit(self, datos: pd.DataFrame):
        """Segmento 1 = FPD (regla de negocio); K-Means segmenta el resto (segmentos 2..k+1)."""
        self.fpd_ = bool(es_fpd(datos).any())
        datos = preparar(datos[~es_fpd(datos)])
        self.escalador_ = StandardScaler().fit(datos[VARIABLES_SEGMENTO])
        self.kmeans_ = KMeans(n_clusters=self.k, n_init=20, random_state=SEMILLA).fit(
            self.escalador_.transform(datos[VARIABLES_SEGMENTO]))
        self.mediana_p_ = float(datos["prob_recuperar"].median())
        self.mediana_saldo_ = float(datos["saldo_log"].median())

        centros = pd.DataFrame(self.escalador_.inverse_transform(self.kmeans_.cluster_centers_),
                               columns=VARIABLES_SEGMENTO)
        centros["prob_recuperar"] = 1 / (1 + np.exp(-centros["logit_p"]))
        centros["nivel_p"] = np.where(centros["prob_recuperar"] >= self.mediana_p_, "alta", "baja")
        centros["nivel_saldo"] = np.where(centros["saldo_log"] >= self.mediana_saldo_, "alto", "bajo")
        # Orden: de mayor a menor valor esperado del centroide -> segmento_id 1 = el más valioso
        centros["ve_centro"] = centros["prob_recuperar"] * np.expm1(centros["saldo_log"])
        centros = centros.sort_values("ve_centro", ascending=False).reset_index(names="cluster")
        centros["segmento_id"] = np.arange(1, len(centros) + 1) + (1 if self.fpd_ else 0)

        nombres, vistos = [], {}
        for _, c in centros.iterrows():
            base = ACCIONES[(c["nivel_p"], c["nivel_saldo"])]["nombre"]
            vistos[base] = vistos.get(base, 0) + 1
            nombres.append(base if vistos[base] == 1 else f"{base} {vistos[base]}")
        centros["nombre"] = nombres
        self.centros_ = centros
        self.mapa_ = dict(zip(centros["cluster"], centros["segmento_id"]))
        return self

    def predict(self, datos: pd.DataFrame) -> np.ndarray:
        cl = self.kmeans_.predict(self.escalador_.transform(preparar(datos)[VARIABLES_SEGMENTO]))
        seg = np.vectorize(self.mapa_.get)(cl)
        return np.where(es_fpd(datos).to_numpy() & self.fpd_, 1, seg)

    def tabla_segmentos(self) -> pd.DataFrame:
        """Catálogo para la tabla segmentos de PostgreSQL."""
        filas = []
        if self.fpd_:
            filas.append({"segmento_id": 1, "nombre": ACCION_FPD["nombre"],
                          "descripcion": ACCION_FPD["descripcion"],
                          "accion_sugerida": ACCION_FPD["accion"], "canal_sugerido": ACCION_FPD["canal"]})
        for _, c in self.centros_.iterrows():
            a = ACCIONES[(c["nivel_p"], c["nivel_saldo"])]
            filas.append({"segmento_id": int(c["segmento_id"]), "nombre": c["nombre"],
                          "descripcion": f"{a['descripcion']} (P media centro {c['prob_recuperar']:.2f}; "
                                         f"saldo centro USD {np.expm1(c['saldo_log']):,.0f})",
                          "accion_sugerida": a["accion"], "canal_sugerido": a["canal"]})
        return pd.DataFrame(filas)


def valor_esperado(prob: np.ndarray, saldo: np.ndarray, tasa_media: float,
                   canal: pd.Series) -> pd.DataFrame:
    """Monto esperado bruto, costo del canal y valor esperado neto (supuestos simulados)."""
    cat = pd.DataFrame(CANALES).set_index("nombre")
    costo = canal.map(cat["costo_por_contacto_usd"]).to_numpy(dtype=float)
    efect = canal.map(cat["efectividad_supuesta"]).fillna(0).to_numpy(dtype=float)
    bruto = prob * tasa_media * saldo
    return pd.DataFrame({"monto_esperado": bruto, "costo_gestion": costo,
                         "valor_esperado": bruto * efect - costo})
