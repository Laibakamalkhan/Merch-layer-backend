import compileall
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
raise SystemExit(0 if compileall.compile_dir(str(ROOT/"src"),quiet=1) else 1)
