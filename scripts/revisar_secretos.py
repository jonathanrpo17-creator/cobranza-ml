"""
Revisión de seguridad ANTES de hacer público el repositorio.

Busca en TODO el historial de Git (no solo en los archivos actuales):
  1. Archivos que nunca debieron subirse (.env, kaggle.json, datos crudos, modelos pesados).
  2. Textos con forma de secreto (tokens de Kaggle, contraseñas reales en variables PG_*).

Uso (desde la raíz del proyecto):
    python scripts/revisar_secretos.py
"""
import re
import subprocess
import sys

ARCHIVOS_PROHIBIDOS = [
    (re.compile(r"(^|/)\.env$"), "archivo .env con credenciales"),
    (re.compile(r"kaggle\.json$"), "credenciales de Kaggle"),
    (re.compile(r"^data/(raw|interim|processed)/"), "datos (deben descargarse, no versionarse)"),
    (re.compile(r"\.(csv|parquet|zip)$") , None),  # se revisan aparte por tamaño
]
# (filtro para git -G en sintaxis POSIX, patrón exacto en Python, motivo)
PATRONES = [
    ("KGAT_", re.compile(r"KGAT_[0-9a-fA-F]{16,}"), "token de Kaggle"),
    ('"key"', re.compile(r'"key"\s*:\s*"[0-9a-f]{20,}"'), "clave de kaggle.json"),
    ("PASSWORD=", re.compile(r"PG_(BI_)?PASSWORD=\S+"), "contraseña de PostgreSQL"),
    ("postgres", re.compile(r"postgres(ql)?(\+psycopg2)?://[^:\s/]+:[^@\s]+@"), "URL de conexión con contraseña"),
]
VALORES_DE_EJEMPLO = {"KGAT_tu_token_aqui", "PG_PASSWORD=cambia_esta_clave",
                      "PG_BI_PASSWORD=cambia_esta_otra_clave"}
TAMANO_MAXIMO_MB = 20


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace").stdout


def main() -> int:
    if not git("rev-parse", "--is-inside-work-tree").strip():
        print("❌ Ejecuta este script dentro del repositorio (carpeta cobranza-ml).")
        return 1

    problemas = []

    # 1. Archivos en cualquier commit del historial
    historial = set(filter(None, git("log", "--all", "--pretty=format:", "--name-only").splitlines()))
    for ruta in sorted(historial):
        for patron, motivo in ARCHIVOS_PROHIBIDOS:
            if motivo and patron.search(ruta):
                problemas.append(f"Archivo en el historial: {ruta}  →  {motivo}")

    # 2. Archivos grandes en el historial
    objetos = git("rev-list", "--objects", "--all").splitlines()
    for linea in objetos:
        partes = linea.split(" ", 1)
        if len(partes) == 2:
            tam = git("cat-file", "-s", partes[0]).strip()
            if tam.isdigit() and int(tam) > TAMANO_MAXIMO_MB * 1024 ** 2:
                problemas.append(f"Archivo pesado en el historial: {partes[1]} ({int(tam) / 1024 ** 2:.0f} MB)")

    # 3. Textos con forma de secreto en TODAS las versiones de TODOS los archivos
    for filtro, patron, motivo in PATRONES:
        salida = git("log", "--all", "-p", "-G", filtro, "--pretty=format:@@COMMIT %h %s")
        commit = ""
        for linea in salida.splitlines():
            if linea.startswith("@@COMMIT"):
                commit = linea[9:]
            elif linea.startswith("+") and not linea.startswith("+++"):
                for m in patron.finditer(linea):
                    valor = m.group(0).rstrip("\"',;}) ")
                    if valor not in VALORES_DE_EJEMPLO:
                        problemas.append(f"{motivo} en el commit {commit}: {valor[:14]}…")

    # 4. .env actual protegido
    if git("check-ignore", ".env").strip() != ".env":
        problemas.append(".env NO está ignorado por Git: revisa .gitignore")

    print(f"Commits revisados: {git('rev-list', '--all', '--count').strip()} | "
          f"archivos en el historial: {len(historial)}\n")
    if problemas:
        print(f"❌ Se encontraron {len(set(problemas))} problemas. NO hagas público el repositorio todavía:\n")
        for p in sorted(set(problemas)):
            print("  -", p)
        return 1
    print("✅ Sin secretos, datos ni archivos pesados en el historial. El repositorio se puede hacer público.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
