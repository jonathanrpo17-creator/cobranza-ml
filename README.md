# Optimización de cobranza y recuperación de cartera con aprendizaje por segmentos

> Proyecto II — Especialización en Ciencia de Datos e IA. *(README en construcción: se completa en la Fase 10.)*

## Problema
Las áreas de cobranza contactan a todos los deudores en mora con el mismo esfuerzo. Este proyecto estima qué clientes pagarán con un recordatorio, cuáles requieren negociación con un asesor y cuáles son de baja recuperación, para asignar canales (WhatsApp, llamada, SMS) y asesores donde más rinden. **Métrica de negocio:** cartera recuperada por peso invertido en cobranza.

## Enfoque (resumen)
- **Etapa A:** clasificación — ¿se recupera algo del crédito en mora?
- **Etapa B:** regresión — ¿cuánto se recupera?
- **Etapa C:** valor esperado = P(recuperar) × E[monto] − costo de gestión.
- **Segmentación:** K-Means sobre el valor esperado y perfil del deudor.
- **Simulación de campaña:** canales y costos simulados con supuestos documentados (Prosper no trae datos de gestión).

## Arquitectura
`Kaggle → Python (notebooks + src/) → PostgreSQL → Power BI Desktop + app Streamlit` *(diagrama en Fase 4).*

## Estructura del repositorio
```
data/       datos (no se suben; ver data/README.md)
notebooks/  notebooks numerados por fase (01_entorno, 02_datos, ...)
src/        código reutilizable (limpieza, variables, métricas, ROI)
sql/        esquema de base de datos, índices y vistas
models/     modelos entrenados (joblib)
app/        aplicación de consulta (Streamlit)
powerbi/    dashboard .pbix y PDF exportado
tests/      pruebas automáticas
docs/       documentación, figuras y sustentación
```

## Cómo reproducirlo (Windows)
```powershell
git clone https://github.com/<usuario>/cobranza-ml.git
cd cobranza-ml
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # y completar credenciales
```
Luego ejecutar los notebooks en orden numérico.

## Resultados
*Pendiente (Fases 6–8).*

## Limitaciones
- Datos de Prosper (EE. UU.); canales, costos y efectividad de gestión son **simulados**.

## Equipo
*Pendiente.*
