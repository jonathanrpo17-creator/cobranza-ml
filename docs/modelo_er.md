# Modelo de datos — Arquitectura de la base PostgreSQL

![Diagrama entidad-relación](figuras/04_modelo_er.png)

<details>
<summary>Código fuente del diagrama (Mermaid; GitHub lo dibuja automáticamente)</summary>

```mermaid
erDiagram
    DEUDORES ||--|{ CREDITOS : "tiene"
    CREDITOS ||--|| PERFIL_SOLICITUD : "se describe con"
    CREDITOS ||--|| RESULTADOS_RECUPERACION : "termina en"
    CREDITOS ||--o{ PREDICCIONES : "recibe"
    SEGMENTOS ||--o{ PREDICCIONES : "clasifica"
    CAMPANAS ||--|{ CAMPANA_ASIGNACIONES : "asigna"
    CREDITOS ||--o{ CAMPANA_ASIGNACIONES : "participa en"
    CANALES ||--o{ CAMPANA_ASIGNACIONES : "usa"

    DEUDORES {
        int deudor_id PK
        varchar member_key UK
        smallint creditos_en_cobranza
        date primera_originacion
    }
    CREDITOS {
        int credito_id PK
        varchar loan_key UK
        int deudor_id FK
        date fecha_originacion
        smallint plazo_meses
        numeric monto_original
        numeric tasa_interes
        varchar prosper_rating
        smallint cuota_primer_default
        varchar estado_credito "fuga: solo filtro"
        date fecha_cierre "fuga: solo madurez"
    }
    PERFIL_SOLICITUD {
        int credito_id PK,FK
        varchar situacion_laboral
        varchar rango_ingresos
        numeric ingreso_mensual
        numeric relacion_deuda_ingreso
        smallint puntaje_bureau_min
        smallint moras_7_anios
        smallint prosper_creditos_previos
    }
    RESULTADOS_RECUPERACION {
        int credito_id PK,FK
        numeric exposicion_castigo
        numeric recuperacion_total
        smallint objetivo_a "0 o 1"
        numeric objetivo_b_tasa "0 a 1"
        boolean en_modelado
        varchar conjunto
    }
    PREDICCIONES {
        bigint prediccion_id PK
        int credito_id FK
        varchar modelo_version
        boolean es_vigente
        numeric prob_recuperar
        numeric monto_esperado
        numeric valor_esperado
        smallint segmento_id FK
        int prioridad
    }
    SEGMENTOS {
        smallint segmento_id PK
        varchar nombre UK
        varchar accion_sugerida
        varchar canal_sugerido
    }
    CANALES {
        smallint canal_id PK
        varchar nombre UK
        numeric costo_por_contacto_usd
        numeric efectividad_supuesta
        text fuente_supuesto
    }
    CAMPANAS {
        int campana_id PK
        varchar escenario "sin_modelo o con_modelo"
        jsonb supuestos
    }
    CAMPANA_ASIGNACIONES {
        int campana_id PK,FK
        int credito_id PK,FK
        smallint canal_id FK
        numeric costo_usd
        numeric recuperacion_simulada
    }
```
</details>

## Tablas y propósito

| Grupo | Tabla | Grano (una fila por…) | Se llena en |
|---|---|---|---|
| Datos de origen | `deudores` | persona (MemberKey) | Fase 4 |
| | `creditos` | crédito en cobranza | Fase 4 |
| | `perfil_solicitud` | crédito (foto del deudor al solicitar) | Fase 4 |
| Desenlace | `resultados_recuperacion` | crédito (objetivos A y B) | Fase 4 |
| Catálogos | `segmentos`, `canales` | segmento / canal | Fases 7–8 |
| Modelo | `predicciones` | crédito × versión del modelo | Fases 6–7 |
| Simulación | `campanas`, `campana_asignaciones` | campaña / crédito × campaña | Fase 8 |

Vistas de consumo: `vw_cartera_cobranza` (una fila por crédito, para Power BI y la aplicación) y `vw_resumen_cohortes` (resumen por año de cierre y estado).

## Decisiones de diseño y su justificación

**1. `deudores` separado de `creditos` (relación 1:N).** Un mismo deudor puede tener varios créditos en cobranza (el dataset completo tiene 113.066 créditos y 90.831 deudores). Separarlos evita repetir datos y prepara el caso real: en cobranza se gestiona a la **persona**, no al crédito suelto.

**2. `perfil_solicitud` separado de `deudores` (relación 1:1 con `creditos`).** Ingresos, empleo y puntaje de bureau son una **foto tomada en cada solicitud**: cambian de un crédito a otro. Dependen del crédito, no de la persona, y por eso van con el crédito (tercera forma normal). También separa las condiciones del producto de la información personal, lo que facilita dar permisos distintos.

**3. `resultados_recuperacion` aislado.** Contiene las columnas con **fuga de datos** (LP_*) y las variables objetivo. Tenerlas en una tabla aparte hace visible la regla anti-fuga: el modelo lee sus entradas de `creditos` y `perfil_solicitud`, y el objetivo de aquí.

**4. `predicciones` con versión del modelo.** La llave `(credito_id, modelo_version)` permite guardar varias versiones y comparar modelos sin borrar historia. El campo `es_vigente` indica cuál usan el dashboard y la aplicación.

**5. Canales y campañas como tablas, con los supuestos documentados.** Prosper no trae datos de gestión de cobranza, así que todo lo relativo a canales es **simulado**. `canales.fuente_supuesto` y `campanas.supuestos` (JSONB) dejan trazado cada supuesto de costo y efectividad.

**6. Reglas de calidad dentro de la base.**
- Llaves foráneas: no puede existir un crédito sin deudor.
- `UNIQUE`: no hay créditos ni deudores duplicados.
- `CHECK`: el objetivo A solo vale 0 o 1; las tasas y probabilidades están entre 0 y 1; los montos no son negativos.

El notebook 04 inserta datos inválidos a propósito y verifica que la base los **rechace**.

**7. Llaves sustitutas enteras** (`credito_id`, `deudor_id`) además de las llaves naturales de Prosper (`loan_key`, `member_key`). Hacen más rápidas las uniones y desacoplan el modelo de los identificadores del proveedor de datos.

**8. Índices pensados para las consultas reales.** Incluyen la partición temporal (`fecha_cierre`), el ranking de priorización (`valor_esperado DESC`) y dos índices parciales: la población de modelado y la predicción vigente.

**9. Vistas como capa de consumo.** Power BI y la aplicación leen vistas, no tablas. Si el esquema cambia, se ajusta la vista y el dashboard no se rompe.

**10. Mínimo privilegio.** El rol `lector_bi` (Power BI y aplicación) solo puede **leer las vistas y los catálogos**. No puede ver `perfil_solicitud` directamente ni modificar datos. Las contraseñas viven en `.env` y nunca en el repositorio. Esto es coherente con el principio de seguridad de la Ley 1581 de 2012 (Habeas Data).

**11. Reproducible e idempotente.** `sql/01–05` más el notebook 04 reconstruyen la base desde cero, y se pueden ejecutar varias veces sin duplicar datos.

## ¿Por qué PostgreSQL y por qué local?

- **PostgreSQL:** es relacional, gratuito y robusto. Soporta llaves foráneas, restricciones `CHECK`, índices parciales, `JSONB` y roles. Power BI Desktop se conecta de forma nativa.
- **Local:** no tiene costo, no expone datos a internet y la base se reconstruye desde el repositorio en minutos.
- **Ruta de expansión:** el mismo esquema funciona sin cambios en un PostgreSQL administrado en la nube (Cloud SQL, Azure Database o Amazon RDS) cuando haga falta acceso multiusuario.
