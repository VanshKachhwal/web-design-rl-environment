"""Layer-B tests for the validation study core (light, stub judge, no network).

These exercise the *claims* the study makes — aggregate monotonicity, oracle
ceiling, degenerate floor — on a small ladder with a constant ``StubJudgeClient``
so there are no live API calls and the run stays fast. The full report (every
ladder, real judge, plots) is the script's job, not the suite's.
"""

import numpy as np
from PIL import Image, ImageDraw

from webdesign_rl.grade import perturb, study
from webdesign_rl.grade.judge import StubJudgeClient
from webdesign_rl.grade.perturb import _legible_font


def _reference_image():
    """A realistic page: colored header/footer, light body, legible dark text.

    Having real OCR-able text and a non-trivial palette is what makes the floor
    check honest — a blank/solid degenerate then genuinely fails the content and
    color terms instead of trivially matching an all-white image.
    """
    img = Image.new("RGB", (640, 480), (232, 234, 246))
    draw = ImageDraw.Draw(img)
    font = _legible_font(40)
    draw.rectangle([0, 0, 640, 120], fill=(40, 53, 147))         # header band
    draw.text((24, 35), "Welcome Home", fill=(255, 255, 255), font=font)
    draw.rectangle([24, 150, 310, 400], fill=(255, 243, 224))    # left card
    draw.rectangle([330, 150, 616, 400], fill=(200, 230, 201))   # right card
    draw.text((40, 180), "Get Started", fill=(20, 20, 20), font=font)
    draw.text((350, 180), "Build Tools", fill=(20, 20, 20), font=font)
    draw.rectangle([0, 420, 640, 480], fill=(26, 26, 26))        # footer band
    draw.text((24, 428), "Contact Us", fill=(255, 255, 255), font=font)
    return img


# A neutral mid-rubric stub: a constant judge so design_judge can't drive the
# trend — the deterministic terms must carry the monotonicity on their own.
def _stub():
    return StubJudgeClient(
        {
            "layout_alignment": 5,
            "color_palette": 5,
            "typography": 5,
            "content_completeness": 5,
        }
    )


def test_image_ladder_aggregate_reward_is_monotonic_in_severity():
    ref = _reference_image()
    severities = [0.0, 0.25, 0.5, 0.75, 1.0]
    rewards = [
        study.score_image_variant(perturb.gaussian_blur(ref, s), ref, _stub())[
            "reward"
        ]
        for s in severities
    ]
    corr = study.rank_correlation(severities, rewards)
    # Reward falls as severity rises: strong negative rank correlation.
    assert corr < -0.9, (corr, rewards)


def test_oracle_reference_scores_near_one():
    ref = _reference_image()
    # The perfect-rubric judge + identical image => aggregate ≈ 1.0.
    perfect = StubJudgeClient(
        {k: 10 for k in ("layout_alignment", "color_palette", "typography", "content_completeness")}
    )
    reward = study.score_image_variant(ref, ref, perfect)["reward"]
    assert reward > 0.99


# A judge that honestly rates a degenerate near 0 — the realistic behavior the
# live AnthropicJudgeClient exhibits on a blank/solid/lorem page.
def _floor_judge():
    return StubJudgeClient(
        {k: 0 for k in ("layout_alignment", "color_palette", "typography", "content_completeness")}
    )


def test_degenerates_score_at_the_aggregate_floor():
    ref = _reference_image()
    size = ref.size
    faithful = study.score_image_variant(ref, ref, _stub())["reward"]
    for degenerate in (
        perturb.blank_page(size),
        perturb.solid_color(size),
        perturb.lorem_ipsum(size),
    ):
        reward = study.score_image_variant(degenerate, ref, _floor_judge())["reward"]
        # The blend floors every degenerate far below a faithful candidate — even
        # though a single term (color, or SSIM on a light page) can be generous:
        # content and the judge collapse, and no one term can rescue the blend.
        assert reward < 0.45, reward
        assert reward < faithful - 0.3, (reward, faithful)


def test_solid_gray_color_term_is_generous_but_aggregate_floors_it():
    # Documents the issue-02 caveat numerically: `color` alone is lenient on a
    # mean-gray fill, yet the aggregate floors the variant well below faithful.
    ref = _reference_image()
    faithful = study.score_image_variant(ref, ref, _stub())["reward"]
    gray = perturb.solid_color(ref.size, (128, 128, 128))
    scored = study.score_image_variant(gray, ref, _floor_judge())
    assert scored["color"] > 0.4              # color is generous to mean-gray...
    assert scored["reward"] < faithful - 0.3  # ...but the blend floors it.


def test_degrading_one_page_lowers_the_five_page_site_reward(site5, tmp_path):
    refs = site5["reference_images"]
    page_map = site5["page_map"]

    # Oracle: the unperturbed reference site scores ~1.0 across pages.
    oracle = study.score_site_variant(site5["dir"], refs, page_map, _stub())

    # Degrade exactly one page (delete its visible text) and re-render.
    degraded_dir = perturb.delete_text(site5["dir"], tmp_path / "deg", 1.0)
    # delete_text only edited index.html's text; restore the others by copy is
    # already done (it copied the whole site), so only `home` is degraded.
    degraded = study.score_site_variant(degraded_dir, refs, page_map, _stub())

    # The deterministic content term on the degraded page drags the site reward
    # down: one bad page in five lowers the aggregate.
    assert degraded["reward"] < oracle["reward"]
    assert oracle["reward"] > 0.85
