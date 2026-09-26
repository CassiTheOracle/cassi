import runpy
import sys
import types


core = runpy.run_path("src/mind_field_core.py", init_globals={"value": 9})
module = types.ModuleType("mind_field_core")
module.__dict__.update(core)
sys.modules["mind_field_core"] = module
runtime = runpy.run_path("src/field_runtime.py", init_globals={"value": 9})
assert runtime["result"] == 46
