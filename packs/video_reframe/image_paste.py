"""Paste an original image back onto an outpainted master without a visible seam (numpy only, no ComfyUI imports).

Outpainting models (Bria Expand and the like) return the original redrawn inside the new canvas: their copy of it is
usually a little softer and a few levels darker or lighter than the real thing, and their own join between that copy
and the generated area can sit a few pixels inside the original's edge. Pasting the original back with a fixed narrow
feather leaves that brightness step visible as a thin line. Here, on every side where the original meets generated
pixels:

1. Tone match (optional): the low-frequency difference between the original and the model's copy, measured in a band
   just inside the edge (blurred lightly across the seam and heavily along it), is added to the model's copy in that
   band, and its value at the edge is carried out into the generated area, fading out over about 8 x the blend width. The generated side
   then meets the original at the original's own brightness.
2. Blend: the original fades in over a width that follows the image size: a Gaussian of `seam` x the original's short
   side, centred 3 of those inside the edge, so the original's own pixels reach 99.9% weight about 6 of them in.

Sides that touch the master's border (no generated pixels there) get neither. Everything beyond the blend band is the
original, pixel for pixel."""
import math

import numpy as np


def _box(a, r, axis):
    """Box blur of radius r along axis, edges clamped."""
    if r <= 0 or a.shape[axis] == 0:
        return a
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis, dtype=np.float64)
    n = a.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return ((hi - lo) / (2 * r + 1)).astype(np.float32)


def gauss(a, sigma, axis):
    """Gaussian blur (three box passes) of standard deviation ~sigma along axis, edges clamped."""
    if sigma < 0.5:
        return a
    r = max(1, int(round((math.sqrt(4 * sigma * sigma + 1) - 1) / 2)))
    for _ in range(3):
        a = _box(a, r, axis)
    return a


def _phi(t):
    """Standard normal CDF, vectorised."""
    return 0.5 * (1.0 + np.vectorize(math.erf)(t / math.sqrt(2.0)))


def paste_back(master, original, x, y, seam=0.02, tone_match=True):
    """master: (H, W, C) float array, the outpainted canvas at full size; original: (h, w, C), placed with its top-left
    corner at (x, y) of the master. Returns (out, info)."""
    M = np.asarray(master, np.float32)
    O = np.asarray(original, np.float32)
    H, W, C = M.shape
    h, w = O.shape[:2]
    if O.shape[2] != C:
        O = O[..., :C] if O.shape[2] > C else np.concatenate([O] + [O[..., -1:]] * (C - O.shape[2]), axis=2)
    # clip the original to the canvas
    ox0, oy0 = max(0, -x), max(0, -y)
    X0, Y0 = max(0, x), max(0, y)
    X1, Y1 = min(W, x + w), min(H, y + h)
    if X1 <= X0 or Y1 <= Y0:
        return M.copy(), {"pasted": False}
    O = O[oy0:oy0 + (Y1 - Y0), ox0:ox0 + (X1 - X0)]
    h, w = O.shape[:2]
    s = max(2.0, float(seam) * min(w, h))
    band = int(min(math.ceil(7 * s), w // 2 if w > 1 else 1, h // 2 if h > 1 else 1))
    sides = {"left": X0 > 0, "right": X1 < W, "top": Y0 > 0, "bottom": Y1 < H}
    out = M.copy()
    R = M[Y0:Y1, X0:X1]                         # the model's copy of the original
    Rc = R.copy()                               # its tone-matched version
    weight = np.ones((h, w), np.float32)        # the original's weight
    edge_offsets = {}

    for side, on in sides.items():
        if not on:
            continue
        # views that put this side's seam on the left (index 0 = the edge), rows along the seam
        if side in ("left", "right"):
            t = (lambda a: a) if side == "left" else (lambda a: a[:, ::-1])
            # column 0 = next to the edge
            fill_t = out[Y0:Y1, :X0][:, ::-1] if side == "left" else out[Y0:Y1, X1:]
            k = np.arange(w, dtype=np.float32)
            wk = _phi((k - 3 * s) / s)
            weight *= t(np.broadcast_to(wk, (h, w)))
            along_axis, across_axis = 0, 1
        else:
            t = (lambda a: np.swapaxes(a, 0, 1)) if side == "top" else (lambda a: np.swapaxes(a[::-1], 0, 1))
            # (w, rows) with column 0 next to the edge
            fill_t = np.swapaxes(out[:Y0, X0:X1][::-1], 0, 1) if side == "top" else np.swapaxes(out[Y1:, X0:X1], 0, 1)
            k = np.arange(h, dtype=np.float32)
            wk = _phi((k - 3 * s) / s)
            weight *= np.broadcast_to((wk if side == "top" else wk[::-1])[:, None], (h, w))
            along_axis, across_axis = 0, 1
        if not tone_match:
            continue
        Ob, Rb = t(O)[:, :band], t(R)[:, :band]
        D = Ob - Rb
        # along the seam only, and narrowly: the model's own join inside the band is sharp, and the offset changes
        # with the content (sky vs water), so wide smoothing carries one area's offset into the next
        D = gauss(D, 0.5 * s, along_axis)
        # the model's copy inside the band, matched to the original's low frequencies
        cb = t(Rc)
        cb[:, :band] += D
        e = D[:, 0]                              # offset at the edge, per row along the seam
        edge_offsets[side] = [round(float(v) * 255, 2) for v in e.mean(0)]
        n = fill_t.shape[1]
        if n:
            d = np.arange(1, n + 1, dtype=np.float32)
            fall = np.exp(-(d / min(float(n), 8 * s)) ** 2)   # fades out within ~8 seams, never streaks far
            fill_t += e[:, None, :] * fall[None, :, None]
    np.clip(out, 0, 1, out=out)
    np.clip(Rc, 0, 1, out=Rc)
    wt = weight[..., None]
    out[Y0:Y1, X0:X1] = Rc * (1 - wt) + O * wt
    full = weight >= 0.999                       # the original itself, untouched
    out[Y0:Y1, X0:X1][full] = O[full]
    return out, {"pasted": True, "sigma": round(s, 1), "band": band, "seam_sides": [k for k, v in sides.items() if v],
                 "edge_offset_levels": edge_offsets}
