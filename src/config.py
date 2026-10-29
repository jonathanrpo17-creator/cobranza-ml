"""
Configuración central del proyecto.

Todos los notebooks y la aplicación importan las rutas y credenciales desde aquí,
así nadie escribe rutas "a mano" (C:\\Users\\...) que solo funcionan en un computador.

Uso:
    from src.config import RUTAS, obtener_url_postgres
"""
from __future__ import annotations

from pathlib import Path
import os

from dotenv import load_dotenv

# Raíz del repositorio = carpeta padre de src/
RAIZ = Path(__file__).resolve().parents[1]

# Carga las variables del archivo .env (si existe)
load_dotenv(RAIZ / ".env")

# Rutas del proyecto
RUTAS = {
    "raiz": RAIZ,
    "data_raw": RAIZ / "data" / "raw",
    "data_interim": RAIZ / "data" / "interim",
    "data_processed": RAIZ / "data" / "processed",
    "models": RAIZ / "models",
    "sql": RAIZ / "sql",
    "docs": RAIZ / "docs",
    "figuras": RAIZ / "docs" / "figuras",
}

# Semilla fija para que los resultados sean reproducibles
SEMILLA = 42


def crear_carpetas() -> None:
    """Crea las carpetas de datos/resultados si no existen."""
    for ruta in RUTAS.values():
        ruta.mkdir(parents=True, exist_ok=True)


def obtener_url_postgres(base: str | None = None, rol: str = "admin"):
    """
    Construye la URL de conexión a PostgreSQL leyendo el .env (desde la Fase 4).

    - base: nombre de la base; por defecto PG_DB. Se usa 'postgres' solo para crear la base.
    - rol: 'admin' (PG_USER, carga los datos) o 'lector' (PG_BI_USER, solo lectura,
      para Power BI y la aplicación).

    Se usa URL.create (y no un texto armado a mano) para que una contraseña con
    caracteres como @, : o # no rompa la conexión.
    """
    from sqlalchemy.engine import URL

    usuario_var, clave_var = ("PG_USER", "PG_PASSWORD") if rol == "admin" else ("PG_BI_USER", "PG_BI_PASSWORD")
    requeridas = ["PG_HOST", "PG_PORT", "PG_DB", usuario_var, clave_var]
    faltantes = [v for v in requeridas if not os.getenv(v)]
    if faltantes:
        raise EnvironmentError(
            f"Faltan variables en .env: {faltantes}. Revisa .env.example y completa tu .env."
        )
    return URL.create(
        "postgresql+psycopg2",
        username=os.getenv(usuario_var),
        password=os.getenv(clave_var),
        host=os.getenv("PG_HOST"),
        port=int(os.getenv("PG_PORT")),
        database=base or os.getenv("PG_DB"),
    )
