"""Deterministic similarity metrics for the grader.

Each metric takes a candidate and reference image and returns a float in [0, 1],
where 1.0 means a perfect match. Issue 01 implemented ``structure`` (SSIM); issue
02 adds ``color`` (palette + CIEDE2000). ``content`` and ``design_judge`` arrive
in later issues.
"""

import numpy as np
from PIL import Image
from scipy.cluster.vq import kmeans2
from skimage.color import deltaE_ciede2000, rgb2lab
from skimage.metrics import structural_similarity

# Number of dominant palette colors extracted per image.
_PALETTE_K = 6
# Cap on pixels fed to k-means; larger images are downsampled for speed while
# keeping clustering deterministic. Fixed so the same image always samples the
# same pixels.
_MAX_PIXELS = 4096
# Fixed seed for k-means so the palette (and therefore the score) is identical
# across runs — determinism is a hard requirement for the reward.
_SEED = 0


def structure(candidate_img: Image.Image, reference_img: Image.Image) -> float:
    """Grayscale single-scale SSIM between two images, mapped to [0, 1].

    The candidate is resized to the reference's dimensions so the whole design
    is compared (a height/width mismatch becomes a fair squash penalty). Both
    images are converted to grayscale first, keeping ``structure`` orthogonal to
    the ``color`` term so layout is not double-counted against color.
    """
    reference_gray = np.asarray(reference_img.convert("L"))
    candidate_resized = candidate_img.resize(
        reference_img.size, Image.Resampling.BILINEAR
    )
    candidate_gray = np.asarray(candidate_resized.convert("L"))

    score = structural_similarity(candidate_gray, reference_gray)
    # SSIM is in [-1, 1]; clamp to [0, 1] for a well-formed reward dimension.
    return float(max(0.0, min(1.0, score)))


def _palette(img: Image.Image):
    """Extract a dominant palette from ``img`` as (Lab colors, frequencies).

    Pixels are deterministically downsampled (a fixed stride, capped at
    ``_MAX_PIXELS``) and clustered with k-means (``kmeans2``, fixed ``seed``) into
    up to ``_PALETTE_K`` colors. The returned arrays are the cluster centers in
    Lab space and each cluster's pixel-frequency weight (summing to 1).
    """
    pixels = np.asarray(img.convert("RGB"), dtype=np.float64).reshape(-1, 3)

    # Deterministic downsample: a fixed stride keeps the same pixels every run.
    if len(pixels) > _MAX_PIXELS:
        stride = len(pixels) // _MAX_PIXELS
        pixels = pixels[::stride]

    # Cap clusters at the number of distinct colors so kmeans2 stays stable on
    # near-uniform images (e.g. a solid color has a single palette entry).
    n_distinct = len(np.unique(pixels, axis=0))
    k = min(_PALETTE_K, n_distinct)

    centroids, labels = kmeans2(
        pixels, k, seed=_SEED, minit="++", missing="warn"
    )

    # Frequency weight per surviving (non-empty) cluster.
    counts = np.bincount(labels, minlength=len(centroids)).astype(np.float64)
    keep = counts > 0
    centroids = centroids[keep]
    weights = counts[keep] / counts[keep].sum()

    # Convert the RGB centroids (0-255) to Lab for perceptual ΔE.
    lab = rgb2lab((centroids / 255.0).reshape(1, -1, 3)).reshape(-1, 3)
    return lab, weights


def color(candidate_img: Image.Image, reference_img: Image.Image) -> float:
    """Palette-level color fidelity via frequency-weighted CIEDE2000, in [0, 1].

    A dominant ~6-color palette is extracted from each image with a fixed-seed
    k-means (deterministic). Each candidate palette color is matched to its
    nearest reference color in Lab space (CIEDE2000), and the per-color ΔE is
    averaged **weighted by the candidate cluster frequencies** — so the colors
    that occupy more of the candidate dominate the score, and a candidate that
    devotes lots of area to an off-palette color is penalized accordingly.

    The mean ΔE is normalized as ``max(0, 1 - ΔE / 100)``: identical palettes
    score ≈ 1.0 and the score falls smoothly as the palette drifts. Because it
    compares palettes (not pixels or means), an image with the right *average*
    color but the wrong *palette* scores low — it is not gameable by mean color.
    """
    cand_lab, cand_w = _palette(candidate_img)
    ref_lab, _ = _palette(reference_img)

    # Nearest reference color (in CIEDE2000) for each candidate color.
    nearest = np.empty(len(cand_lab))
    for i, lab in enumerate(cand_lab):
        deltas = deltaE_ciede2000(
            np.broadcast_to(lab, ref_lab.shape), ref_lab
        )
        nearest[i] = deltas.min()

    mean_delta = float(np.average(nearest, weights=cand_w))
    return max(0.0, 1.0 - mean_delta / 100.0)
