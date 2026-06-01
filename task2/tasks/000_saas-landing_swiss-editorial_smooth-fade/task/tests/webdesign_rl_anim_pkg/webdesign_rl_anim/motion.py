"""The deterministic ``motion`` term: how faithfully a candidate's animation
*moves* like the reference's, over the filmstrip.

The two other animation signals lean on the static grader (the settled frame's
4 terms) and a VLM (feel/timing). ``motion`` is the cheap, fully-deterministic
backbone: it compares the **spatio-temporal motion signature** of the two
filmstrips — *where* on the page things change, *when* across the strip, and *how
much*.

Signature: downsample each frame to a coarse luminance grid (averaging away text
detail and exact geometry), take the absolute difference between consecutive
frames → a ``(K-1, rows, cols)`` tensor of per-cell change-over-time. Two
filmstrips are compared on:

* **pattern** — cosine similarity of the flattened tensors (matches *where/when*
  motion happens, scale-free), and
* **magnitude** — the ratio of total motion energy (penalises a candidate that
  moves far too little — e.g. a *static* page — or far too much).

``motion = pattern * magnitude``. An identical candidate scores 1.0; a static
candidate scores ~0 (no energy); a wrong-timing candidate, sampled at the same
absolute times, diverges on both factors. No model call, no randomness.
"""

import numpy as np
from PIL import Image

# Coarse signature grid as PIL ``resize`` size = (cols, rows). 16x12 ≈ 192 cells:
# fine enough to localise which region animates (hero vs cards vs footer), coarse
# enough that exact text/pixels and small layout offsets don't dominate.
_GRID = (16, 12)


def _signature(frames, grid=_GRID):
    """``(K-1, rows, cols)`` tensor of per-cell luminance change between frames."""
    small = []
    for frame in frames:
        gray = frame.convert("L").resize(grid, Image.BILINEAR)
        small.append(np.asarray(gray, dtype=np.float32) / 255.0)
    arr = np.stack(small)            # (K, rows, cols)
    return np.abs(arr[1:] - arr[:-1])  # (K-1, rows, cols)


def motion_score(ref_frames, cand_frames) -> float:
    """Score candidate-vs-reference motion fidelity in [0, 1].

    Both filmstrips MUST be sampled at the same absolute timestamps (the grader
    guarantees this) and have the same length. Returns 0.0 if the strips can't be
    compared (length mismatch / fewer than 2 frames).
    """
    if len(ref_frames) != len(cand_frames) or len(ref_frames) < 2:
        return 0.0

    ref_sig = _signature(ref_frames).ravel()
    cand_sig = _signature(cand_frames).ravel()

    energy_ref = float(ref_sig.sum())
    energy_cand = float(cand_sig.sum())
    peak = max(energy_ref, energy_cand)
    if peak <= 1e-6:
        # Both filmstrips are effectively static. Degenerate, but "equally still"
        # is a faithful match, so don't punish it.
        return 1.0

    magnitude = min(energy_ref, energy_cand) / peak
    norm = np.linalg.norm(ref_sig) * np.linalg.norm(cand_sig)
    pattern = float(np.dot(ref_sig, cand_sig) / norm) if norm > 0 else 0.0
    pattern = max(0.0, pattern)  # cosine is non-negative here, but be defensive

    return float(magnitude * pattern)
