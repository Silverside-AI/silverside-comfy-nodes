"""Silverside Comfy Nodes: the custom nodes Silverside's finished Brand Brain workflows use, as one ComfyUI pack.

Each part under packs/ is one former pack, kept as its own Python package (see packs.json for where it came from).
This loader:
  - imports every part on its own, so one failing import is reported and the other parts still load;
  - refuses a node name that two parts (or ComfyUI's own nodes) would both define, instead of letting one silently
    replace the other;
  - registers only the AutoMatte nodes finished workflows use (packs/automatte_allowlist.json); AutoMatte's other
    nodes belong to workflows still in progress.
All frontend files live in web/ (one WEB_DIRECTORY for the whole pack).
"""
import importlib
import json
import logging
import os

log = logging.getLogger("silverside_comfy_nodes")
HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = ["automatte", "image_finish", "mask_aspect_crop", "photo_projection_3d", "product_label_refinement", "video_extend",
         "video_reframe", "video_trimmer"]

with open(os.path.join(HERE, "packs", "automatte_allowlist.json")) as f:
    AUTOMATTE_ALLOW = set(json.load(f))

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
LOADED, FAILED = [], {}

try:                                    # ComfyUI's own node names, to never shadow one
    import nodes as _comfy_nodes
    _CORE = set(getattr(_comfy_nodes, "NODE_CLASS_MAPPINGS", {}))
except Exception:
    _CORE = set()

for part in PARTS:
    try:
        mod = importlib.import_module(f".packs.{part}", __name__)
    except Exception as e:              # report it and carry on: the other parts still load
        FAILED[part] = f"{type(e).__name__}: {e}"
        log.error("Silverside Comfy Nodes: part %s did not load: %s", part, FAILED[part])
        continue
    classes = dict(getattr(mod, "NODE_CLASS_MAPPINGS", {}) or {})
    names = dict(getattr(mod, "NODE_DISPLAY_NAME_MAPPINGS", {}) or {})
    if part == "automatte":
        classes = {k: v for k, v in classes.items() if k in AUTOMATTE_ALLOW}
    for key, cls in classes.items():
        if key in NODE_CLASS_MAPPINGS or key in _CORE:
            log.error("Silverside Comfy Nodes: node %r from %s is already defined; skipped", key, part)
            continue
        NODE_CLASS_MAPPINGS[key] = cls
        if key in names:
            NODE_DISPLAY_NAME_MAPPINGS[key] = names[key]
    LOADED.append(part)

WEB_DIRECTORY = "./web"
log.info("Silverside Comfy Nodes: %d nodes from %s%s", len(NODE_CLASS_MAPPINGS), ", ".join(LOADED),
         ("; failed: " + ", ".join(FAILED)) if FAILED else "")

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
