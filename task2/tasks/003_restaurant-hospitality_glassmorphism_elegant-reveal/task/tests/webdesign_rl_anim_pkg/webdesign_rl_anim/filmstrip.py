"""Build a labelled *contact sheet* from a filmstrip.

A contact sheet stacks the filmstrip's frames vertically at a uniform width with
a ``t=<ms>`` caption above each. It's the single-image view of an animation we
hand to (a) the agent — alongside the individual frame PNGs — so it can read the
motion off one picture, and (b) the animation VLM judge, so a whole filmstrip is
one image instead of N (keeping the judge call to two images: reference sheet +
candidate sheet).
"""

from PIL import Image, ImageDraw

# Uniform thumbnail width for each stacked frame, the caption strip height, and
# padding. Kept modest so a 6-frame sheet of tall pages stays well under the
# vision API's per-image ceiling.
_THUMB_W = 460
_LABEL_H = 26
_PAD = 8
_BG = (245, 245, 248)
_INK = (30, 30, 40)


def contact_sheet(frames, timestamps_ms, *, thumb_w: int = _THUMB_W) -> Image.Image:
    """Stack ``frames`` vertically at ``thumb_w`` with a ``t=<ms>`` caption each.

    Args:
        frames: list of PIL images (any size; aspect ratio preserved).
        timestamps_ms: one label per frame (same length as ``frames``).
        thumb_w: uniform width each frame is scaled to.

    Returns:
        One RGB contact-sheet image.
    """
    thumbs = []
    for frame in frames:
        w, h = frame.size
        scaled_h = max(1, round(h * thumb_w / w))
        thumbs.append(frame.convert("RGB").resize((thumb_w, scaled_h), Image.LANCZOS))

    total_h = sum(_LABEL_H + t.height + _PAD for t in thumbs) + _PAD
    sheet = Image.new("RGB", (thumb_w + 2 * _PAD, total_h), _BG)
    draw = ImageDraw.Draw(sheet)

    y = _PAD
    for thumb, t in zip(thumbs, timestamps_ms):
        draw.text((_PAD, y + 6), f"t = {t} ms", fill=_INK)
        y += _LABEL_H
        sheet.paste(thumb, (_PAD, y))
        y += thumb.height + _PAD
    return sheet
