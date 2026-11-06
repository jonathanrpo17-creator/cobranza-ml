# Carpeta `data/`

Esta carpeta **no se sube a GitHub** (está en `.gitignore`). Cada integrante debe descargar los datos en su propio computador.

## Fuente

- Dataset: **Prosper Loan Data** (Kaggle)
- URL: https://www.kaggle.com/datasets/yousuf28/prosper-loan
- Origen: Prosper Marketplace (EE. UU.), préstamos persona a persona.

## Cómo descargarlo

**Opción A — automática (recomendada):** ejecutar `notebooks/02_datos.ipynb`. Usa `kagglehub` con el token de tu archivo `.env` (`KAGGLE_API_TOKEN`; se genera en Kaggle → Settings → API → Create New Token).

**Opción B — manual:** entrar a la URL, clic en *Download*, descomprimir y copiar el CSV dentro de `data/raw/`.

## Estructura esperada

```
data/
├── raw/        # archivo original de Kaggle, sin modificar
├── interim/    # resultados intermedios (limpieza, población objetivo)
└── processed/  # tablas listas para modelar
```
