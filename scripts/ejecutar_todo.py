"""
Reproduce el proyecto completo ejecutando los notebooks en orden.

Uso (desde la raíz del proyecto, con .venv activo y PostgreSQL encendido):
    python scripts/ejecutar_todo.py              # del 01 al 09
    python scripts/ejecutar_todo.py --desde 05   # retomar desde un notebook
    python scripts/ejecutar_todo.py --hasta 04   # solo hasta la base de datos

Cada notebook se ejecuta "en limpio" (kernel nuevo) y se guarda con sus salidas.
Si uno falla, se detiene y dice cuál y por qué: así se garantiza que el
proyecto funciona de principio a fin, no solo celda por celda.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
NOTEBOOKS = sorted((RAIZ / "notebooks").glob("[0-9][0-9]_*.ipynb"))


def main() -> int:
    p = argparse.ArgumentParser(description="Ejecuta los notebooks del proyecto en orden.")
    p.add_argument("--desde", default="01", help="Número del primer notebook (ej. 05)")
    p.add_argument("--hasta", default="99", help="Número del último notebook (ej. 09)")
    p.add_argument("--timeout", type=int, default=1800, help="Segundos máximos por celda")
    args = p.parse_args()

    seleccion = [nb for nb in NOTEBOOKS if args.desde <= nb.name[:2] <= args.hasta]
    if not seleccion:
        print("No hay notebooks en ese rango.")
        return 1

    print(f"Se ejecutarán {len(seleccion)} notebooks:\n  " + "\n  ".join(nb.name for nb in seleccion) + "\n")
    inicio_total = time.time()
    for nb in seleccion:
        inicio = time.time()
        print(f"▶ {nb.name} ...", end=" ", flush=True)
        r = subprocess.run(
            [sys.executable, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute", "--inplace",
             f"--ExecutePreprocessor.timeout={args.timeout}", "--ExecutePreprocessor.kernel_name=python3",
             str(nb)],
            cwd=RAIZ / "notebooks", capture_output=True, text=True)
        if r.returncode != 0:
            print("❌")
            print(f"\nFalló {nb.name}. Últimas líneas del error:\n")
            print("\n".join((r.stderr or r.stdout).strip().splitlines()[-25:]))
            print(f"\nCorrige el problema y retoma con:  python scripts/ejecutar_todo.py --desde {nb.name[:2]}")
            return 1
        print(f"✅ ({time.time() - inicio:.0f} s)")
    print(f"\n✅ Proyecto reproducido de principio a fin en {(time.time() - inicio_total) / 60:.1f} minutos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
