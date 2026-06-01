"""Build the per-task model-eval report for a Task-2 (animation) Harbor job.

Task-2 mirror of Task 1's ``scripts/report.py``.

The five **data sections** (Task 1's items 1-5) render in both formats:

    1. Provenance header (task id, seed tuple, animation style, model, executor,
       trials, cost/tokens, wall-clock, filmstrip timestamps, date, commit).
    2. Per-trial score table + a summary row (median / mean +/- std / min / max).
    3. Reward distribution + per-term distributions.
    4. Per-term mean bars (+/- std).
    5. Per-page x per-term heatmap (mean across trials).

The two **visual galleries** (Task 1's items 6-7) render in **markdown mode only**,
as animated **GIFs** built from the saved filmstrip frames (GitHub renders GIFs
inline; base64-in-HTML would bloat the file, so the HTML report stays sections
1-5):

    6. Worst per metric — for each term, the worst-scoring (trial, page) as a
       reference|candidate GIF pair.
    7. Best-overall attempt vs reference — the highest-reward trial's reference|
       candidate GIF pair for every page.

Terms are the animation page-reward terms ``static_design / motion /
animation_judge`` (Task 1's four static terms are preserved nested under each
page in ``scores.json`` for drill-down). Alongside the report it writes the
harvest contract ``scores.json`` + ``scores.csv``. The plot/table/selection data
all come from the unit-tested pure core in :mod:`aggregate_results_anim`.

This module is the **untested shell** (matplotlib + GIF/PIL + HTML/markdown
assembly); the data behind every table/plot/gallery-selection is the unit-tested
pure core in that harvester.

Run::

    PYTHONPATH=task2 .venv/bin/python -m webdesign_rl_anim.report_anim jobs/anim-aurora-001
    PYTHONPATH=task2 .venv/bin/python -m webdesign_rl_anim.report_anim jobs/anim-aurora-001 \
      --out task2/reports/anim-aurora-001 --format markdown
"""

import argparse
import base64
import html
import io
import sys
from pathlib import Path

import matplotlib
import numpy as np
from PIL import Image

matplotlib.use("Agg")  # headless: no display, deterministic PNG output.
import matplotlib.pyplot as plt  # noqa: E402

from . import aggregate_results_anim as agg  # noqa: E402

# GIF gallery defaults (markdown mode). 480px / 128 colours ≈ 0.5 MB/GIF on a
# tall page. The GIF shows exactly the SIX graded frames (the 0–2000 ms window
# the motion term is evaluated on), at their real inter-frame timing, looping —
# the settled/at-rest frame is NOT included (it's graded by static_design, not one
# of the six). Loop ≈ the 2 s window + a short hold on the final frame.
GIF_WIDTH = 480
GIF_COLORS = 128
_GIF_END_HOLD_MS = 400   # final (last graded) frame held a beat before looping

# Distinct hues for the three animation terms (motion is the discriminating one,
# so it gets the warm/attention colour).
TERM_COLORS = {
    "static_design": "#283593",   # indigo — the reused Task-1 static third
    "motion": "#c62828",          # red — the deterministic motion signature
    "animation_judge": "#ef6c00",  # orange — the VLM feel/timing term
}


# --- plots -> base64 PNG data URIs / files ------------------------------------


def _fig_to_data_uri(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _fig_to_file(fig, path, dpi=110):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def _img_tag(data_uri, alt):
    return f'<img src="{data_uri}" alt="{html.escape(alt)}" />'


def _fig_distributions(scores):
    """Item 3: reward distribution (box + strip) + per-term box plots."""
    rewards = agg.reward_series(scores)
    dists = agg.per_term_distributions(scores)
    terms = scores["terms"]

    fig, (ax_r, ax_t) = plt.subplots(1, 2, figsize=(12, 4.5),
                                     gridspec_kw={"width_ratios": [1, 2.2]})

    ax_r.boxplot([rewards], orientation="vertical", widths=0.5,
                 patch_artist=True, boxprops={"facecolor": "#c5cae9"})
    jitter = 1 + (np.random.default_rng(0).uniform(-0.06, 0.06, len(rewards)))
    ax_r.scatter(jitter, rewards, color="#283593", zorder=3, s=28)
    ax_r.set_xticks([1])
    ax_r.set_xticklabels(["reward"])
    ax_r.set_ylim(0, 1.02)
    ax_r.set_ylabel("score")
    ax_r.set_title("Reward distribution")
    ax_r.grid(True, axis="y", alpha=0.3)

    data = [dists[t] for t in terms]
    bp = ax_t.boxplot(data, orientation="vertical", widths=0.6, patch_artist=True)
    for patch, term in zip(bp["boxes"], terms):
        patch.set_facecolor(TERM_COLORS.get(term, "#999"))
        patch.set_alpha(0.45)
    ax_t.set_xticks(range(1, len(terms) + 1))
    ax_t.set_xticklabels(terms)
    ax_t.set_ylim(0, 1.02)
    ax_t.set_title("Per-term distributions")
    ax_t.grid(True, axis="y", alpha=0.3)

    fig.tight_layout()
    return fig


def _fig_per_term_means(scores):
    """Item 4: per-term mean bars with +/- std error bars."""
    ms = agg.per_term_mean_std(scores)
    terms = scores["terms"]
    means = [ms[t]["mean"] for t in terms]
    stds = [ms[t]["std"] for t in terms]
    colors = [TERM_COLORS.get(t, "#999") for t in terms]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(terms, means, yerr=stds, capsize=6, color=colors, alpha=0.85)
    for bar, m in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, m + 0.02,
                f"{m:.3f}", ha="center", fontsize=10)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("mean score (+/- std)")
    ax.set_title("Per-term mean (animation skill shape)")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def _fig_page_term_heatmap(scores):
    """Item 5: per-page x per-term heatmap (mean across trials)."""
    matrix = agg.per_page_term_matrix(scores)
    pages = matrix["pages"]
    terms = matrix["terms"]
    values = np.asarray(matrix["values"], dtype=float)

    fig, ax = plt.subplots(figsize=(1.6 + 1.3 * len(terms),
                                    1.2 + 0.5 * max(len(pages), 1)))
    im = ax.imshow(values, cmap="RdYlGn", vmin=0.0, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(terms)))
    ax.set_xticklabels(terms, rotation=30, ha="right")
    ax.set_yticks(range(len(pages)))
    ax.set_yticklabels(pages)
    for i in range(len(pages)):
        for j in range(len(terms)):
            v = values[i, j]
            if v == v:  # not NaN
                ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                        fontsize=8, color="black")
    ax.set_title("Per-page x per-term (mean across trials)")
    fig.colorbar(im, ax=ax, shrink=0.8, label="score")
    fig.tight_layout()
    return fig


# --- HTML assembly ------------------------------------------------------------


def _prov_rows(meta):
    """The provenance (label, value) rows shared by the HTML + markdown headers."""
    seed = meta.get("seed_tuple")
    seed_str = " / ".join(seed) if seed else None
    wall = meta.get("wall_clock_sec")
    wall_str = f"{wall / 60:.1f} min" if wall is not None else None
    cost = meta.get("total_cost_usd")
    cost_str = f"${cost:.2f}" if cost is not None else None
    ts = meta.get("timestamps_ms")
    ts_str = ", ".join(str(t) for t in ts) if ts else None
    aac = [meta.get("archetype"), meta.get("aesthetic"), meta.get("complexity")]
    aac_str = " / ".join(str(x) for x in aac) if any(x is not None for x in aac) else None
    return [
        ("Task", meta.get("task_id")),
        ("Seed tuple", seed_str),
        ("Archetype / Aesthetic / Complexity", aac_str),
        ("Animation style", meta.get("animation_style")),
        ("Model", meta.get("model")),
        ("Agent", meta.get("agent")),
        ("Executor", meta.get("executor")),
        ("Trials", meta.get("n_trials")),
        ("Cost", cost_str),
        ("Input tokens", meta.get("total_input_tokens")),
        ("Output tokens", meta.get("total_output_tokens")),
        ("Wall-clock", wall_str),
        ("Filmstrip timestamps (ms)", ts_str),
        ("Date", meta.get("date")),
        ("Repo commit", meta.get("commit")),
    ]


def _provenance_html(meta):
    """Item 1: provenance header as a definition list."""
    def fmt(v):
        return html.escape(str(v)) if v is not None else "&mdash;"

    items = "\n".join(f"<dt>{html.escape(k)}</dt><dd>{fmt(v)}</dd>"
                      for k, v in _prov_rows(meta))
    return f"<dl class='prov'>\n{items}\n</dl>"


def _score_table_html(scores):
    """Item 2: per-trial score table + a summary row."""
    terms = scores["terms"]
    cols = ["reward", *terms]
    header = "".join(f"<th>{html.escape(c)}</th>" for c in cols)

    body_rows = []
    for trial in scores["trials"]:
        cells = "".join(f"<td>{trial[c]:.3f}</td>" for c in cols)
        body_rows.append(f"<tr><td>{html.escape(trial['trial_id'])}</td>{cells}</tr>")

    summaries = {c: agg.summary_stats([t[c] for t in scores["trials"]]) for c in cols}
    summary_cells = []
    for c in cols:
        s = summaries[c]
        summary_cells.append(
            f"<td>med {s['median']:.3f}<br>{s['mean']:.3f}&plusmn;{s['std']:.3f}"
            f"<br>[{s['min']:.3f}, {s['max']:.3f}]</td>"
        )
    summary_row = f"<tr class='summary'><td>summary</td>{''.join(summary_cells)}</tr>"

    return (
        "<table class='scores'>"
        f"<thead><tr><th>trial</th>{header}</tr></thead>"
        f"<tbody>{''.join(body_rows)}{summary_row}</tbody>"
        "</table>"
    )


def render_html(scores):
    """Assemble the full self-contained ``report.html`` string (items 1-5)."""
    meta = scores["meta"]
    title = f"Animation model-eval report — {html.escape(str(meta.get('task_id')))}"

    dist_uri = _fig_to_data_uri(_fig_distributions(scores))
    means_uri = _fig_to_data_uri(_fig_per_term_means(scores))
    heatmap_uri = _fig_to_data_uri(_fig_page_term_heatmap(scores))

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; margin: 2rem;
          color: #222; max-width: 960px; }}
  h1 {{ font-size: 1.5rem; }}
  h2 {{ font-size: 1.15rem; margin-top: 2rem; border-bottom: 1px solid #ddd;
        padding-bottom: 0.3rem; }}
  dl.prov {{ display: grid; grid-template-columns: max-content 1fr;
             gap: 0.2rem 1rem; }}
  dl.prov dt {{ font-weight: 600; color: #555; }}
  table.scores {{ border-collapse: collapse; width: 100%; font-variant-numeric:
                  tabular-nums; }}
  table.scores th, table.scores td {{ border: 1px solid #ddd; padding: 0.35rem
                                      0.6rem; text-align: right; }}
  table.scores th:first-child, table.scores td:first-child {{ text-align: left; }}
  table.scores tr.summary {{ background: #f4f4f8; font-size: 0.85rem; }}
  img {{ max-width: 100%; height: auto; }}
</style></head>
<body>
<h1>{title}</h1>

<h2>1. Provenance</h2>
{_provenance_html(meta)}

<h2>2. Per-trial scores</h2>
{_score_table_html(scores)}

<h2>3. Reward + per-term distributions</h2>
{_img_tag(dist_uri, "reward and per-term distributions")}

<h2>4. Per-term means</h2>
{_img_tag(means_uri, "per-term mean bars")}

<h2>5. Per-page x per-term heatmap</h2>
{_img_tag(heatmap_uri, "per-page per-term heatmap")}
</body></html>
"""


# --- Markdown assembly (GitHub-native: report.md + PNG files) -----------------


def _provenance_md(meta):
    lines = ["| field | value |", "|---|---|"]
    for k, v in _prov_rows(meta):
        lines.append(f"| {k} | {v if v is not None else '—'} |")
    return "\n".join(lines)


def _score_table_md(scores):
    terms = scores["terms"]
    cols = ["reward", *terms]
    rows = ["| trial | " + " | ".join(cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for t in scores["trials"]:
        rows.append("| " + t["trial_id"] + " | "
                    + " | ".join(f"{t[c]:.3f}" for c in cols) + " |")
    summ = {c: agg.summary_stats([t[c] for t in scores["trials"]]) for c in cols}
    rows.append("| **summary** | " + " | ".join(
        f"med {summ[c]['median']:.3f} · {summ[c]['mean']:.3f}±{summ[c]['std']:.3f}"
        for c in cols) + " |")
    return "\n".join(rows)


# --- GIF galleries (markdown mode, items 6-7) ---------------------------------
#
# Build an animated GIF per (trial, page, ref|cand) from the saved filmstrip
# frames, so the gallery shows the *motion* a still PNG can't. GitHub renders
# animated GIFs inline in markdown. Untested shell (PIL/IO); which cells to show
# is the pure selection logic in ``aggregate_results_anim``.


def _trial_dir(job_dir, trial_id):
    """The trial dir whose short id matches ``trial_id`` (names vary in Task 2)."""
    for d in agg._trial_dirs(Path(job_dir)):
        if agg._trial_id(d) == trial_id:
            return d
    return None


def _build_gif(renders_dir, page, who, timestamps, dst, *, width, colors):
    """Assemble a page's six graded filmstrip frames into a looping GIF.

    Shows exactly the frames the motion term is evaluated on — the 0–2000 ms
    window — at their real inter-frame timing, with the final graded frame held
    one short beat so it reads before looping (loop ≈ 2.4 s). The settled/at-rest
    frame is deliberately NOT included: it is graded by static_design, not one of
    the six motion frames. All frames share one palette (from the final frame) to
    avoid inter-frame colour flicker. Returns True on success, False when the
    frames are absent (caller emits a placeholder).
    """
    renders_dir = Path(renders_dir)
    frame_paths = [renders_dir / f"{page}_{who}_t{t:05d}.png" for t in timestamps]
    frame_paths = [p for p in frame_paths if p.exists()]
    if not frame_paths:
        return False

    imgs = [Image.open(p).convert("RGB") for p in frame_paths]
    height = round(imgs[0].height * width / imgs[0].width)
    imgs = [im.resize((width, height), Image.LANCZOS) for im in imgs]
    palette = imgs[-1].convert("P", palette=Image.ADAPTIVE, colors=colors)
    paletted = [im.quantize(palette=palette, dither=Image.FLOYDSTEINBERG)
                for im in imgs]

    # Real inter-frame gaps for frames 0..n-2; the last graded frame held a beat.
    ts = list(timestamps)[:len(frame_paths)]
    durations = ([max(80, ts[i + 1] - ts[i]) for i in range(len(ts) - 1)]
                 + [_GIF_END_HOLD_MS])

    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    paletted[0].save(dst, save_all=True, append_images=paletted[1:],
                     duration=durations, loop=0, optimize=True, disposal=2)
    return True


def _gif_link(job_dir, trial_id, page, who, timestamps, out_dir, cache, *, width, colors):
    """Markdown link to the ``(trial, page, who)`` GIF, building it once and reusing.

    The GIF for a given (trial, page, ref|cand) is identical no matter which
    section asks for it, so it is content-addressed by that triple and cached —
    §6 and §7 referencing the same cell share one file (no duplicate weight).
    """
    key = (trial_id, page, who)
    if key in cache:
        return cache[key]
    rel = f"images/{trial_id}_{page}_{who}.gif"
    tdir = _trial_dir(job_dir, trial_id)
    ok = tdir is not None and _build_gif(
        tdir / "verifier" / "renders", page, who, timestamps,
        Path(out_dir) / rel, width=width, colors=colors,
    )
    link = f"![{who} {page}]({rel})" if ok else "_(no render)_"
    cache[key] = link
    return link


def _per_metric_gallery_md(scores, job_dir, out_dir, cache, *, width, colors):
    """Item 6: each term's worst (trial, page) as a reference|candidate GIF pair."""
    extrema = agg.per_metric_extrema(scores)
    ts = scores.get("timestamps_ms") or []
    block = ["## 6. Worst per metric (reference vs candidate)", ""]
    for term in scores["terms"]:
        ex = extrema.get(term)
        if ex is None:
            continue
        w = ex["worst"]
        ref = _gif_link(job_dir, w["trial_id"], w["page"], "ref", ts, out_dir,
                        cache, width=width, colors=colors)
        cand = _gif_link(job_dir, w["trial_id"], w["page"], "cand", ts, out_dir,
                         cache, width=width, colors=colors)
        block += [
            f"**{term}** — worst page `{w['page']}` "
            f"(trial `{w['trial_id']}`, score {w['score']:.3f})", "",
            "| reference | candidate |", "|---|---|",
            f"| {ref} | {cand} |", "",
        ]
    return "\n".join(block)


def _best_overall_gallery_md(scores, job_dir, out_dir, cache, *, width, colors):
    """Item 7: the best-overall trial's reference|candidate GIF pair, every page."""
    tid = agg.best_overall_trial(scores)
    trial = next((t for t in scores["trials"] if t["trial_id"] == tid), None)
    if trial is None:
        return ""
    ts = scores.get("timestamps_ms") or []
    block = ["## 7. Best-overall attempt vs reference (all pages)", "",
             f"Best-overall trial `{tid}` (reward {trial['reward']:.3f}).", "",
             "| page | reference | candidate |", "|---|---|---|"]
    for page, pdata in trial["pages"].items():
        if not pdata.get("present", True):
            continue
        ref = _gif_link(job_dir, tid, page, "ref", ts, out_dir, cache,
                        width=width, colors=colors)
        cand = _gif_link(job_dir, tid, page, "cand", ts, out_dir, cache,
                         width=width, colors=colors)
        block.append(f"| {page} | {ref} | {cand} |")
    return "\n".join(block)


def _galleries_md(scores, job_dir, out_dir, *, width, colors):
    """Items 6-7 as GIF galleries, or "" when the job has no persisted frames.

    A shared cache content-addresses each ``(trial, page, who)`` GIF so a cell
    referenced by both galleries is built (and stored) only once.
    """
    if job_dir is None or not agg.gallery_available(job_dir):
        return ""
    cache = {}
    metric = _per_metric_gallery_md(scores, job_dir, out_dir, cache,
                                    width=width, colors=colors)
    overall = _best_overall_gallery_md(scores, job_dir, out_dir, cache,
                                       width=width, colors=colors)
    return f"\n{metric}\n\n{overall}\n"


def render_markdown(scores, out_dir, job_dir=None, *,
                    gif_width=GIF_WIDTH, gif_colors=GIF_COLORS):
    """Write ``report.md`` + sibling plot PNGs (and, with ``job_dir``, GIF galleries).

    The five data sections always render. Items 6-7 (the GIF galleries) render
    only when ``job_dir`` has persisted ``verifier/renders/`` frames; otherwise
    they are omitted and the report degrades to the data sections.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = scores["meta"]

    _fig_to_file(_fig_distributions(scores), out_dir / "distributions.png")
    _fig_to_file(_fig_per_term_means(scores), out_dir / "per_term_means.png")
    _fig_to_file(_fig_page_term_heatmap(scores), out_dir / "heatmap.png")

    galleries = (_galleries_md(scores, job_dir, out_dir,
                               width=gif_width, colors=gif_colors)
                 if job_dir is not None else "")

    md = f"""# Animation model-eval report — {meta.get('task_id')}

## 1. Provenance

{_provenance_md(meta)}

## 2. Per-trial scores

{_score_table_md(scores)}

## 3. Reward + per-term distributions

![reward and per-term distributions](distributions.png)

## 4. Per-term means

![per-term mean bars](per_term_means.png)

## 5. Per-page × per-term heatmap

![per-page per-term heatmap](heatmap.png)
{galleries}"""
    (out_dir / "report.md").write_text(md)
    return out_dir


# --- entry point --------------------------------------------------------------


def build_report(job_dir, out_dir, fmt="html", *,
                 gif_width=GIF_WIDTH, gif_colors=GIF_COLORS):
    """Harvest the job and write scores.json + scores.csv + the report.

    ``fmt`` is ``"html"`` (default, a self-contained ``report.html``, sections
    1-5 only) or ``"markdown"`` (a GitHub-renderable ``report.md`` + sibling plot
    PNGs + the items 6-7 GIF galleries under ``images/``). Both read only the
    normalized harvest from :mod:`aggregate_results_anim`.

    Raises ``ValueError`` if ``job_dir`` is not an animation job (e.g. a Task-1
    static job), rather than emitting a misleading all-zero-terms report.
    """
    job_dir = Path(job_dir)
    if not agg.is_anim_job(job_dir):
        raise ValueError(
            f"{job_dir} is not a Task-2 animation job (no animation grade found). "
            "Use Task 1's scripts/report.py for static design-replication jobs."
        )
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    scores = agg.harvest(job_dir)
    agg.write_scores(scores, out_dir)
    if fmt == "markdown":
        render_markdown(scores, out_dir, job_dir=job_dir,
                        gif_width=gif_width, gif_colors=gif_colors)
    else:
        (out_dir / "report.html").write_text(render_html(scores))
    return out_dir


def _default_out(job_dir):
    return Path("task2") / "reports" / Path(job_dir).name


def main(argv=None):  # pragma: no cover - thin CLI shell
    parser = argparse.ArgumentParser(
        prog="python -m webdesign_rl_anim.report_anim",
        description="Build the per-task animation model-eval report (items 1-5).",
    )
    parser.add_argument("job_dir", help="saved Harbor job dir, e.g. jobs/anim-aurora-001")
    parser.add_argument("--out", default=None,
                        help="output dir (default: task2/reports/<job-name>/)")
    parser.add_argument("--format", choices=["html", "markdown"], default="html",
                        help="self-contained 'html' (default, sections 1-5) or "
                        "GitHub 'markdown' (adds the items 6-7 GIF galleries).")
    parser.add_argument("--gif-width", type=int, default=GIF_WIDTH,
                        help=f"GIF gallery width in px (default {GIF_WIDTH}).")
    parser.add_argument("--gif-colors", type=int, default=GIF_COLORS,
                        help=f"GIF palette size (default {GIF_COLORS}).")
    args = parser.parse_args(argv)

    out_dir = Path(args.out) if args.out else _default_out(args.job_dir)
    build_report(args.job_dir, out_dir, fmt=args.format,
                 gif_width=args.gif_width, gif_colors=args.gif_colors)
    print(f"Report written to {out_dir}")


if __name__ == "__main__":  # pragma: no cover
    main()
