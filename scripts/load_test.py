"""Load Silverside Comfy Nodes the way ComfyUI does and check every node, without installing it anywhere.

    <ComfyUI python> scripts/load_test.py <ComfyUI folder>
    e.g. ~/Documents/ComfyUI/comfyui-test/venv/bin/python scripts/load_test.py ~/Documents/ComfyUI/comfyui-test

Exit 0 = every part loaded, no node refused as a duplicate, every node's inputs and function valid.
This checks loading only; a part's own regression tests run in its source repo.
"""
import importlib.util, logging, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
comfy = os.path.abspath(os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "."))
sys.path.insert(0, comfy); os.chdir(comfy)
records = []
logging.basicConfig(level=logging.INFO)
logging.getLogger("silverside_comfy_nodes").addHandler(type("H", (logging.Handler,), {"emit": lambda s, r: records.append(r.getMessage())})())
import folder_paths  # noqa: E402,F401  ComfyUI's own module, as the parts expect
import server  # noqa: E402  ComfyUI creates its PromptServer before loading nodes; parts that add routes need one
if not hasattr(server.PromptServer, "instance"):
    from aiohttp import web
    server.PromptServer.instance = type("StandIn", (), {"routes": web.RouteTableDef(), "send_sync": lambda *a, **k: None})()

spec = importlib.util.spec_from_file_location("silverside-comfy-nodes", os.path.join(ROOT, "__init__.py"), submodule_search_locations=[ROOT])
m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m; spec.loader.exec_module(m)
bad = []
for key, cls in m.NODE_CLASS_MAPPINGS.items():
    try:
        cls.INPUT_TYPES() if hasattr(cls, "INPUT_TYPES") else cls.define_schema()
        fn = getattr(cls, "FUNCTION", None)
        if fn and not hasattr(cls, fn):
            bad.append(f"{key}: missing {fn}")
    except Exception as e:
        bad.append(f"{key}: {type(e).__name__}: {e}"[:160])
dups = [r for r in records if "already defined" in r]
print(f"parts loaded: {m.LOADED}; failed: {m.FAILED or 'none'}")
print(f"nodes: {len(m.NODE_CLASS_MAPPINGS)}; refused duplicates: {dups or 'none'}; broken: {bad or 'none'}")
sys.exit(1 if (m.FAILED or dups or bad) else 0)
