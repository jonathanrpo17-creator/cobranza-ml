"""
Funciones reutilizables de descarga, carga y revisión de calidad de datos.

Se importan desde los notebooks (02_datos, 03_eda, ...) y luego desde la aplicación,
para que la lógica no viva "atrapada" dentro de un notebook.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from src.config import RUTAS

# Identificador del dataset en Kaggle
DATASET_KAGGLE = "yousuf28/prosper-loan"

# Columnas que SOLO pueden usarse para construir la variable objetivo o el ROI.
# Nunca entran al modelo como predictoras (regla anti-fuga de datos).
COLUMNAS_FUGA = [
    "LP_CustomerPayments",
    "LP_CustomerPrincipalPayments",
    "LP_InterestandFees",
    "LP_ServiceFees",
    "LP_CollectionFees",
    "LP_GrossPrincipalLoss",
    "LP_NetPrincipalLoss",
    "LP_NonPrincipalRecoverypayments",
    "ClosedDate",
]


def descargar_prosper() -> list[Path]:
    """
    Descarga el dataset desde Kaggle con kagglehub y copia los CSV a data/raw/.
    Las credenciales se leen del .env (KAGGLE_USERNAME y KAGGLE_KEY), que
    src.config ya cargó como variables de entorno.
    Devuelve la lista de CSV copiados.
    """
    import kagglehub  # se importa aquí para que el resto del módulo no dependa de Kaggle

    RUTAS["data_raw"].mkdir(parents=True, exist_ok=True)
    carpeta_cache = Path(kagglehub.dataset_download(DATASET_KAGGLE))

    copiados = []
    for csv in carpeta_cache.rglob("*.csv"):
        destino = RUTAS["data_raw"] / csv.name
        shutil.copy2(csv, destino)
        copiados.append(destino)

    if not copiados:
        raise FileNotFoundError(
            f"No se encontraron CSV en {carpeta_cache}. Revisa la descarga o usa la opción manual."
        )
    return copiados


def buscar_csv_crudo() -> Path:
    """Devuelve la ruta del CSV en data/raw/. Falla con un mensaje claro si no hay o si hay varios."""
    archivos = sorted(RUTAS["data_raw"].glob("*.csv"))
    if not archivos:
        raise FileNotFoundError(
            "No hay CSV en data/raw/. Ejecuta descargar_prosper() o copia el archivo manualmente."
        )
    if len(archivos) > 1:
        raise ValueError(f"Hay varios CSV en data/raw/: {[a.name for a in archivos]}. Deja solo el de Prosper.")
    return archivos[0]


def cargar_crudo(ruta: Path | None = None) -> pd.DataFrame:
    """
    Carga el CSV original sin modificar los valores.
    - low_memory=False: pandas lee todo el archivo antes de decidir el tipo de cada
      columna (evita columnas con tipos mezclados).
    - Las columnas cuyo nombre contiene 'Date' se convierten a fecha.
    """
    ruta = ruta or buscar_csv_crudo()
    df = pd.read_csv(ruta, low_memory=False)

    for col in [c for c in df.columns if "date" in c.lower()]:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def perfil_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construye el diccionario técnico de variables: una fila por columna con tipo,
    % de nulos, valores únicos, un ejemplo y un rol preliminar.
    La descripción de negocio se completa en el notebook a partir del diccionario oficial.
    """
    filas = []
    for col in df.columns:
        serie = df[col]
        no_nulos = serie.dropna()
        filas.append({
            "columna": col,
            "tipo": str(serie.dtype),
            "pct_nulos": round(serie.isna().mean() * 100, 2),
            "n_unicos": serie.nunique(dropna=True),
            "ejemplo": no_nulos.iloc[0] if len(no_nulos) else None,
            "rol": "solo_objetivo_o_roi (fuga)" if col in COLUMNAS_FUGA else "por_definir",
            "descripcion": "",
        })
    return pd.DataFrame(filas)


def resumen_calidad(df: pd.DataFrame) -> pd.DataFrame:
    """Indicadores generales de calidad del dataset en una tabla de dos columnas."""
    columnas_clave = [c for c in df.columns if "key" in c.lower()]
    indicadores = {
        "filas": len(df),
        "columnas": df.shape[1],
        "filas_duplicadas_exactas": int(df.duplicated().sum()),
        "columnas_100pct_nulas": int((df.isna().mean() == 1).sum()),
        "columnas_constantes": int((df.nunique(dropna=True) <= 1).sum()),
        "columnas_con_mas_50pct_nulos": int((df.isna().mean() > 0.5).sum()),
        "memoria_mb": round(df.memory_usage(deep=True).sum() / 1024**2, 1),
    }
    for col in columnas_clave:
        indicadores[f"duplicados_en_{col}"] = int(df[col].duplicated().sum())
    return pd.DataFrame(indicadores.items(), columns=["indicador", "valor"])
