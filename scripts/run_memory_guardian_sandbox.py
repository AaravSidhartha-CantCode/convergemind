"""Run the database-free randomized Memory Guardian sandbox.

Use this when FalkorDB or pytest is unavailable on the current machine. The
runner stubs only the unavailable FalkorDB client import; the test then calls
the production verification function with a randomized in-memory graph double.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


if "falkordb" not in sys.modules:
    falkordb_stub = types.ModuleType("falkordb")
    falkordb_stub.FalkorDB = object
    sys.modules["falkordb"] = falkordb_stub


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
test_path = ROOT / "tests" / "test_memory_guardian_sandbox.py"
spec = importlib.util.spec_from_file_location("memory_guardian_sandbox", test_path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Could not load {test_path}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.test_randomized_blast_radius_sandbox()
print("PASS: 75 randomized Memory Guardian blast-radius scenarios")
