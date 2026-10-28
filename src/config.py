"""
Configuración central del proyecto.

Todos los notebooks y la aplicación importan las rutas y credenciales desde aquí,
así nadie escribe rutas "a mano" (C:\\Users\\...) que solo funcionan en un computador.

Uso:
    from src.config import RUTAS, obtener_url_postgres
"""
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


def obtener_url_postgres() -> str:
    """Construye la URL de conexión a PostgreSQL leyendo el .env (se usa desde la Fase 4)."""
    requeridas = ["PG_HOST", "PG_PORT", "PG_DB", "PG_USER", "PG_PASSWORD"]
    faltantes = [v for v in requeridas if not os.getenv(v)]
    if faltantes:
        raise EnvironmentError(
            f"Faltan variables en .env: {faltantes}. Copia .env.example a .env y complétalo."
        )
    return (
        f"postgresql+psycopg2://{os.getenv('PG_USER')}:{os.getenv('PG_PASSWORD')}"
        f"@{os.getenv('PG_HOST')}:{os.getenv('PG_PORT')}/{os.getenv('PG_DB')}"
    )
