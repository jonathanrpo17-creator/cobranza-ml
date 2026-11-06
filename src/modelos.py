"""
Modelos de la Fase 6.

Etapa A (clasificación): ¿se recupera algo?      -> ModeloClasificacion
Etapa B (regresión):     ¿qué % se recupera?     -> ModeloTasa (solo créditos con A=1)

Cada modelo se guarda con joblib como un solo objeto que contiene TODO lo que necesita
para predecir (lista de variables, categorías vistas en entrenamiento, calibrador).
Así la aplicación solo hace:  modelo.predict_proba(X)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import SEMILLA


def particion_interna(fechas: pd.Series, fraccion_final: float = 0.25) -> tuple[np.ndarray, np.ndarray]:
    """
    Divide el ENTRENAMIENTO en dos bloques temporales:
      - ajuste: el 75 % más antiguo (se entrena el modelo)
      - control: el 25 % más reciente (parada temprana y calibración)
    La validación (2010+) nunca se toca para ajustar nada.
    """
    corte = fechas.quantile(1 - fraccion_final)
    control = (fechas > corte).to_numpy()
    return ~control, control


# --------------------------------------------------------------------------
# Preparación de categóricas para LightGBM
# --------------------------------------------------------------------------
class _Categorizador:
    """Fija las categorías vistas en entrenamiento; las nuevas o raras pasan a 'Otro'."""

    def __init__(self, columnas: list[str], min_frecuencia: int = 50):
        self.columnas, self.min_frecuencia = columnas, min_frecuencia

    def fit(self, X: pd.DataFrame):
        self.categorias_ = {}
        for col in self.columnas:
            frec = X[col].astype(str).value_counts()
            self.categorias_[col] = sorted(frec[frec >= self.min_frecuencia].index) + ["Otro"]
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        X = X.copy()
        for col, cats in self.categorias_.items():
            valores = X[col].astype(str).where(X[col].astype(str).isin(cats), "Otro")
            X[col] = pd.Categorical(valores, categories=cats)
        return X


# --------------------------------------------------------------------------
# Etapa A: clasificación
# --------------------------------------------------------------------------
class ModeloClasificacion:
    """
    tipo='logistica' : línea base interpretable (imputación + escalado + one-hot)
    tipo='lightgbm'  : modelo principal (árboles de gradient boosting)
    Ambos se calibran con el bloque de control (calibración de Platt).
    """

    def __init__(self, tipo: str, numericas: list[str], categoricas: list[str],
                 parametros: dict | None = None):
        self.tipo, self.numericas, self.categoricas = tipo, numericas, categoricas
        self.parametros = parametros or {}

    @property
    def variables(self) -> list[str]:
        return self.numericas + self.categoricas

    # --- construcción del estimador ---
    def _crear_estimador(self):
        if self.tipo == "logistica":
            from sklearn.compose import ColumnTransformer
            from sklearn.impute import SimpleImputer
            from sklearn.linear_model import LogisticRegression
            from sklearn.pipeline import Pipeline
            from sklearn.preprocessing import OneHotEncoder, StandardScaler

            prep = ColumnTransformer([
                ("num", Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)),
                                  ("esc", StandardScaler())]), self.numericas),
                ("cat", Pipeline([("imp", SimpleImputer(strategy="constant", fill_value="Sin dato")),
                                  ("ohe", OneHotEncoder(handle_unknown="infrequent_if_exist",
                                                        min_frequency=50))]), self.categoricas),
            ])
            return Pipeline([("prep", prep),
                             ("modelo", LogisticRegression(C=self.parametros.get("C", 0.1),
                                                           max_iter=2000))])
        if self.tipo == "lightgbm":
            from lightgbm import LGBMClassifier

            base = dict(n_estimators=2000, learning_rate=0.02, num_leaves=15,
                        min_child_samples=100, subsample=0.8, subsample_freq=1,
                        colsample_bytree=0.7, reg_lambda=5.0, random_state=SEMILLA, verbose=-1)
            base.update(self.parametros)
            return LGBMClassifier(**base)
        raise ValueError(f"Tipo de modelo desconocido: {self.tipo}")

    def _preparar(self, X: pd.DataFrame) -> pd.DataFrame:
        X = X[self.variables]
        return self.categorizador_.transform(X) if self.tipo == "lightgbm" else X

    # --- entrenamiento ---
    def fit(self, X_ajuste, y_ajuste, X_control, y_control):
        from sklearn.linear_model import LogisticRegression

        self.estimador_ = self._crear_estimador()
        if self.tipo == "lightgbm":
            import lightgbm as lgb

            self.categorizador_ = _Categorizador(self.categoricas).fit(X_ajuste)
            self.estimador_.fit(self._preparar(X_ajuste), y_ajuste,
                                eval_set=[(self._preparar(X_control), y_control)],
                                eval_metric="auc",
                                callbacks=[lgb.early_stopping(100, verbose=False)])
            self.n_arboles_ = self.estimador_.best_iteration_
        else:
            self.estimador_.fit(X_ajuste[self.variables], y_ajuste)

        # Calibración de Platt sobre el bloque de control (datos que el modelo no vio)
        crudo = self._puntaje_crudo(X_control)
        self.calibrador_ = LogisticRegression().fit(crudo.reshape(-1, 1), y_control)
        return self

    def _puntaje_crudo(self, X) -> np.ndarray:
        p = self.estimador_.predict_proba(self._preparar(X))[:, 1]
        p = np.clip(p, 1e-6, 1 - 1e-6)
        return np.log(p / (1 - p))  # logit

    def predict_proba(self, X, calibrada: bool = True) -> np.ndarray:
        crudo = self._puntaje_crudo(X)
        if not calibrada:
            return 1 / (1 + np.exp(-crudo))
        return self.calibrador_.predict_proba(crudo.reshape(-1, 1))[:, 1]


# --------------------------------------------------------------------------
# Etapa B: tasa de recuperación (solo créditos con A=1)
# --------------------------------------------------------------------------
class ModeloTasa:
    """
    tipo='media'    : línea base (predice la tasa promedio de entrenamiento)
    tipo='lightgbm' : LightGBM con objetivo de entropía cruzada, pensado para
                      valores entre 0 y 1: la predicción nunca sale de ese rango.
    """

    def __init__(self, tipo: str, numericas: list[str], categoricas: list[str],
                 parametros: dict | None = None):
        self.tipo, self.numericas, self.categoricas = tipo, numericas, categoricas
        self.parametros = parametros or {}

    @property
    def variables(self) -> list[str]:
        return self.numericas + self.categoricas

    def fit(self, X_ajuste, y_ajuste, X_control, y_control):
        if self.tipo == "media":
            self.media_ = float(np.mean(y_ajuste))
            return self
        import lightgbm as lgb
        from lightgbm import LGBMRegressor

        base = dict(objective="cross_entropy", n_estimators=2000, learning_rate=0.02,
                    num_leaves=15, min_child_samples=60, subsample=0.8, subsample_freq=1,
                    colsample_bytree=0.7, reg_lambda=5.0, random_state=SEMILLA, verbose=-1)
        base.update(self.parametros)
        self.categorizador_ = _Categorizador(self.categoricas, min_frecuencia=30).fit(X_ajuste)
        self.estimador_ = LGBMRegressor(**base)
        self.estimador_.fit(self.categorizador_.transform(X_ajuste[self.variables]), y_ajuste,
                            eval_set=[(self.categorizador_.transform(X_control[self.variables]),
                                       y_control)],
                            eval_metric="l1",
                            callbacks=[lgb.early_stopping(100, verbose=False)])
        self.n_arboles_ = self.estimador_.best_iteration_
        return self

    def predict(self, X) -> np.ndarray:
        if self.tipo == "media":
            return np.full(len(X), self.media_)
        pred = self.estimador_.predict(self.categorizador_.transform(X[self.variables]))
        return np.clip(pred, 0, 1)
