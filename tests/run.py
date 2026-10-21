"""Run every test_* function in tests/ without needing pytest:  python tests/run.py
(The same files also run under pytest.)"""
import importlib.util
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
passed = failed = 0
for f in sorted(Path(__file__).parent.glob("test_*.py")):
    spec = importlib.util.spec_from_file_location(f.stem, f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in [n for n in dir(mod) if n.startswith("test_")]:
        try:
            getattr(mod, name)()
            passed += 1
        except Exception:
            failed += 1
            print(f"FAIL {f.name}::{name}")
            traceback.print_exc()
print(f"{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
