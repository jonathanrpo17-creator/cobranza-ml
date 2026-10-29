# Permite que pytest encuentre el paquete src/ al ejecutarse desde la raíz del proyecto
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
