-- =====================================================================
-- 04_permisos.sql — Principio de mínimo privilegio (gobierno de datos)
--
-- El rol lector_bi lo crea el notebook 04 con la contraseña del .env
-- (las contraseñas nunca se escriben en archivos del repositorio).
-- Aquí solo se definen sus permisos: LEER las vistas, nada más.
-- =====================================================================

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM lector_bi;
GRANT CONNECT ON DATABASE cobranza TO lector_bi;
GRANT USAGE   ON SCHEMA public     TO lector_bi;
GRANT SELECT  ON vw_cartera_cobranza, vw_resumen_cohortes TO lector_bi;
-- Catálogos de solo consulta para el dashboard (sin datos personales)
GRANT SELECT  ON segmentos, canales, campanas, campana_asignaciones TO lector_bi;
