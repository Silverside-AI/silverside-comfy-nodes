# Silverside Comfy Nodes

Silverside's custom ComfyUI nodes, as one pack (81 nodes). This repository is public so ComfyUI builds can install
it from git. It holds node code only: no workflows, examples, manuals or test harnesses. Those stay private.

| Part (`packs/`) | Nodes | From |
|---|---|---|
| `automatte` | 10: soft subject mattes, depth, material passes, edges | ComfyUI-AutoMatte @ c2da6d0 |
| `image_finish` | 3: grain, brightness and colour, optional image | ComfyUI-ImageFinish @ 9ca928f |
| `mask_aspect_crop` | 4: image reframe and composite, crop by mask to aspect, optional image | ComfyUI-MaskAspectCrop @ 1752d49 |
| `photo_projection_3d` | 2: project a photo onto a 3D model, extra views | ComfyUI-PhotoProjection3D @ bb3e8c2 |
| `product_label_refinement` | 37: label refinement, stills and video | ComfyUI-ProductLabelRefinement @ 93b7fed |
| `video_extend` | 8: edge frames, segments and images (optional 16:9 / 9:16 padding), join (speed matching), seam repair, auto resolution, edge motion | ComfyUI-VideoExtend @ a3ad8af |
| `video_reframe` | 7: crop to ratio, outpaint canvas, paste back (video and image), retime | ComfyUI-VideoReframe @ 9db0438 |
| `video_trimmer` | 10: trim, scene split and join, scene gate, video info | ComfyUI-VideoTrimmer @ 1c80a6f |

**Every part is a mirror of a pinned commit of its source repo** (`packs.json` records repo and commit), minus
workflows, examples, READMEs, tools and tests (`scripts/sync_part.py` strips them). Development happens in the source
repos; never edit a part here by hand. Node names are unchanged from the original packs.

## Installing on a build

Add this repository to the build spec **and remove the eight packs it replaces** (ComfyUI-AutoMatte,
ComfyUI-ImageFinish, ComfyUI-MaskAspectCrop, ComfyUI-PhotoProjection3D, ComfyUI-ProductLabelRefinement,
ComfyUI-VideoExtend, ComfyUI-VideoReframe, ComfyUI-VideoTrimmer). With both installed, every node would be defined
twice.

Requirements are in `requirements.txt`. Left to ComfyUI and the build on purpose: torch, torchvision and numpy
(ComfyUI ships them; listing them can make pip replace the build's CUDA torch) and OpenCV (every build already
installs it through other packs; a further variant breaks OpenCV installs).

## How it avoids clashes

- One loader (`__init__.py`) imports each part separately. A part that fails to import is logged and skipped; the
  other parts still load.
- A node name that two parts, or ComfyUI's own nodes, would both define is refused and logged, never silently
  replaced. Checked against the 55 third-party packs on the team and production builds (2026-11-19): no shared node
  names and no shared Python module names.
- Only the AutoMatte nodes in use are registered (`packs/automatte_allowlist.json`).
- All frontend files are in `web/` with unique file and extension names; server routes keep their part's prefix.

## Updating a part (re-sync from its source repo)

1. The change is merged in the part's source repo and tested there.
2. `python3 scripts/sync_part.py <part> <commit>` replaces `packs/<part>/` with that commit, strips what stays
   private, moves its frontend files into `web/`, flags requirements the root `requirements.txt` doesn't cover, and
   records the commit in `packs.json`. A new part: add it to `packs.json` and to `PARTS` in `__init__.py` first.
3. `<ComfyUI python> scripts/load_test.py <ComfyUI folder>`: every part loads, no node refused as a duplicate, every
   node valid. Then commit ("<part> -> <commit>") and push with the owner's OK.

Never commit workflows, keys or `.env` files.
