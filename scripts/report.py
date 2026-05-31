"""Build the per-task model-eval report from any saved Harbor job (EP-03).

Point this at a saved job dir (``jobs/<name>/``) and it writes a self-contained
per-task evidence dashboard — **items 1-5** of the locked v1 report contents
(the scores-and-tables half; the screenshot galleries, items 6-7, are EP-04):

    1. Provenance header (task id, seed tuple, model, executor, trials,
       cost/tokens, wall-clock, date, commit).
    2. Per-trial score table + a summary row (median / mean +/- std / min / max).
    3. Reward distribution + per-term distributions.
    4. Per-term mean bars (+/- std).
    5. Per-page x per-term heatmap (mean across trials).

Alongside ``report.html`` it writes the harvest contract: ``scores.json`` (the
normalized object) + ``scores.csv`` (long-form). Everything the report renders
reads only the normalized object produced by
:func:`webdesign_rl.eval.aggregate_results.harvest`.

This module is the **untested shell** (matplotlib + HTML assembly). The
data behind every table/plot is the unit-tested pure core in
``aggregate_results``. Plots are base64-embedded so ``report.html`` opens with no
server and no sibling asset files.

Run::

    PYTHONPATH=src .venv/bin/python scripts/report.py jobs/opus47-004
    PYTHONPATH=src .venv/bin/python scripts/report.py jobs/opus47-004 --out reports/model-eval/004
"""

import argparse
import base64
import html
import io
import json
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")  # headless: no display, deterministic PNG output.
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from webdesign_rl.eval import aggregate_results as agg  # noqa: E402

TERM_COLORS = {
    "structure": "#283593",
    "color": "#2e7d32",
    "content": "#c62828",
    "design_judge": "#ef6c00",
}


# --- plots -> base64 PNG data URIs --------------------------------------------


def _fig_to_data_uri(fig):
    """Render a matplotlib figure to a base64 ``data:`` URI and close it."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _img_tag(data_uri, alt):
    return f'<img src="{data_uri}" alt="{html.escape(alt)}" />'


def _png_to_data_uri(path):
    """Read a PNG file and base64-embed it as a ``data:`` URI (same scheme as
    plots), keeping ``report.html`` a single self-contained file. ``None`` when
    the file is absent so a missing render degrades to a placeholder."""
    path = Path(path)
    if not path.exists():
        return None
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def plot_distributions(scores):
    """Item 3: reward distribution (strip) + per-term box plots."""
    rewards = agg.reward_series(scores)
    dists = agg.per_term_distributions(scores)
    terms = scores["terms"]

    fig, (ax_r, ax_t) = plt.subplots(1, 2, figsize=(12, 4.5),
                                     gridspec_kw={"width_ratios": [1, 2.2]})

    # Reward: box + jittered strip so the low-variance cluster reads honestly.
    ax_r.boxplot([rewards], orientation="vertical", widths=0.5,
                 patch_artist=True,
                 boxprops={"facecolor": "#c5cae9"})
    jitter = 1 + (np.random.default_rng(0).uniform(-0.06, 0.06, len(rewards)))
    ax_r.scatter(jitter, rewards, color="#283593", zorder=3, s=28)
    ax_r.set_xticks([1])
    ax_r.set_xticklabels(["reward"])
    ax_r.set_ylim(0, 1.02)
    ax_r.set_ylabel("score")
    ax_r.set_title("Reward distribution")
    ax_r.grid(True, axis="y", alpha=0.3)

    # Per-term box plots.
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
    return _fig_to_data_uri(fig)


def plot_per_term_means(scores):
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
    ax.set_title("Per-term mean (skill shape)")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return _fig_to_data_uri(fig)


def plot_page_term_heatmap(scores):
    """Item 5: per-page x per-term heatmap (mean across trials)."""
    matrix = agg.per_page_term_matrix(scores)
    pages = matrix["pages"]
    terms = matrix["terms"]
    values = np.asarray(matrix["values"], dtype=float)

    fig, ax = plt.subplots(figsize=(1.6 + 1.1 * len(terms),
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
    return _fig_to_data_uri(fig)


# --- HTML assembly (items 1-2) ------------------------------------------------


def _provenance_html(meta):
    """Item 1: provenance header as a definition list."""
    def fmt(v):
        return html.escape(str(v)) if v is not None else "&mdash;"

    seed = meta.get("seed_tuple")
    seed_str = " / ".join(seed) if seed else "&mdash;"
    wall = meta.get("wall_clock_sec")
    wall_str = f"{wall / 60:.1f} min" if wall is not None else "&mdash;"
    cost = meta.get("total_cost_usd")
    cost_str = f"${cost:.2f}" if cost is not None else "&mdash;"

    rows = [
        ("Task", meta.get("task_id")),
        ("Seed tuple", seed_str),
        ("Archetype / Aesthetic / Complexity",
         f"{fmt(meta.get('archetype'))} / {fmt(meta.get('aesthetic'))} / "
         f"{fmt(meta.get('complexity'))}"),
        ("Model", meta.get("model")),
        ("Agent", meta.get("agent")),
        ("Executor", meta.get("executor")),
        ("Trials", meta.get("n_trials")),
        ("Cost", cost_str),
        ("Input tokens", meta.get("total_input_tokens")),
        ("Output tokens", meta.get("total_output_tokens")),
        ("Wall-clock", wall_str),
        ("Date", meta.get("date")),
        ("Repo commit", meta.get("commit")),
    ]
    # Pre-formatted string values (seed/wall/cost/composite) are already
    # HTML-safe; everything else is escaped via fmt().
    items = "\n".join(
        f"<dt>{html.escape(k)}</dt><dd>{v if isinstance(v, str) else fmt(v)}</dd>"
        for k, v in rows
    )
    return f"<dl class='prov'>\n{items}\n</dl>"


def _score_table_html(scores):
    """Item 2: per-trial score table + a summary row."""
    terms = scores["terms"]
    cols = ["reward", *terms]
    header = "".join(f"<th>{html.escape(c)}</th>" for c in cols)

    body_rows = []
    for trial in scores["trials"]:
        cells = "".join(f"<td>{trial[c]:.3f}</td>" for c in cols)
        body_rows.append(
            f"<tr><td>{html.escape(trial['trial_id'])}</td>{cells}</tr>"
        )

    # Summary row: median / mean +/- std / min / max for each column.
    summaries = {c: agg.summary_stats([t[c] for t in scores["trials"]]) for c in cols}
    summary_cells = []
    for c in cols:
        s = summaries[c]
        summary_cells.append(
            f"<td>med {s['median']:.3f}<br>"
            f"{s['mean']:.3f}&plusmn;{s['std']:.3f}<br>"
            f"[{s['min']:.3f}, {s['max']:.3f}]</td>"
        )
    summary_row = (
        f"<tr class='summary'><td>summary</td>{''.join(summary_cells)}</tr>"
    )

    return (
        "<table class='scores'>"
        f"<thead><tr><th>trial</th>{header}</tr></thead>"
        f"<tbody>{''.join(body_rows)}{summary_row}</tbody>"
        "</table>"
    )


# --- visual-evidence galleries (items 6-7) ------------------------------------
#
# The galleries bind the grader's numbers to the screenshots behind them: the
# candidate pixels come from the job's persisted ``verifier/renders/<page>.png``
# (the exact renders the grader scored), the reference from the task's baked
# ``tests/reference_site/<screenshot>.png`` (the exact images compared against),
# mapped render-page -> reference via ``tests/page_map.json``. Which renders to
# show is the unit-tested pure selection logic in ``aggregate_results``; loading
# and embedding the PNGs is this untested shell.


def _render_uri(job_dir, trial_id, page):
    """Embed a candidate render: ``task__<id>/verifier/renders/<page>.png``."""
    return _png_to_data_uri(
        Path(job_dir) / f"task__{trial_id}" / "verifier" / "renders" / f"{page}.png"
    )


def _load_page_map(task_path):
    """The task's page -> screenshot map (``tests/page_map.json``), or ``{}``."""
    pm = Path(task_path) / "tests" / "page_map.json"
    if not pm.exists():
        return {}
    try:
        return json.loads(pm.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _reference_uri(task_path, page_map, page):
    """Embed the reference the grader compared ``page`` against.

    Maps the render page key to its reference screenshot via ``page_map`` (the
    filenames need not match) and reads it from ``tests/reference_site/``.
    """
    spec = page_map.get(page)
    if not spec or "screenshot" not in spec:
        return None
    return _png_to_data_uri(
        Path(task_path) / "tests" / "reference_site" / spec["screenshot"]
    )


def _gallery_available(job_dir, task_path):
    """True when the job has persisted renders + a task page_map to map them.

    Jobs that predate EP-01 have no ``verifier/renders/``; the galleries are then
    skipped so the items 1-5 report still builds.
    """
    if not task_path or not _load_page_map(task_path):
        return False
    return any(Path(job_dir).glob("task__*/verifier/renders/*.png"))


def _figure_cell(uri, caption, alt):
    """One labelled image cell (figure) in a gallery row; placeholder if missing."""
    caption_html = caption  # caller pre-escapes / formats the caption
    if uri is None:
        body = "<div class='missing'>(no render)</div>"
    else:
        body = _img_tag(uri, alt)
    return f"<figure>{body}<figcaption>{caption_html}</figcaption></figure>"


def _per_metric_gallery_html(scores, job_dir, task_path, page_map):
    """Item 6: a reference|best|worst triple per term, scored + range-annotated."""
    extrema = agg.per_metric_extrema(scores)
    rows = []
    for term in scores["terms"]:
        ex = extrema.get(term)
        if ex is None:
            continue
        best, worst = ex["best"], ex["worst"]
        lo, hi = ex["range"]
        rng = f"range {lo:.3f}&ndash;{hi:.3f}"

        # The reference is the best render's page (the page it is paired against).
        ref_cell = _figure_cell(
            _reference_uri(task_path, page_map, best["page"]),
            f"reference &middot; {html.escape(best['page'])}",
            f"reference {best['page']}",
        )
        best_cell = _figure_cell(
            _render_uri(job_dir, best["trial_id"], best["page"]),
            f"best &middot; {html.escape(best['trial_id'])}/"
            f"{html.escape(best['page'])} &middot; {best['score']:.3f}",
            f"best {term}",
        )
        worst_cell = _figure_cell(
            _render_uri(job_dir, worst["trial_id"], worst["page"]),
            f"worst &middot; {html.escape(worst['trial_id'])}/"
            f"{html.escape(worst['page'])} &middot; {worst['score']:.3f}",
            f"worst {term}",
        )
        rows.append(
            f"<div class='gallery-row'>"
            f"<h3>{html.escape(term)} <span class='rng'>({rng})</span></h3>"
            f"<div class='triple'>{ref_cell}{best_cell}{worst_cell}</div>"
            f"</div>"
        )
    return "\n".join(rows)


def _best_overall_gallery_html(scores, job_dir, task_path, page_map):
    """Item 7: the best-overall trial's render beside the reference, every page."""
    trial_id = agg.best_overall_trial(scores)
    trial = next((t for t in scores["trials"] if t["trial_id"] == trial_id), None)
    if trial is None:
        return ""

    rows = []
    for page, pdata in trial["pages"].items():
        if not pdata.get("present", True):
            continue
        ref_cell = _figure_cell(
            _reference_uri(task_path, page_map, page),
            f"reference &middot; {html.escape(page)}",
            f"reference {page}",
        )
        cand_cell = _figure_cell(
            _render_uri(job_dir, trial_id, page),
            f"candidate &middot; {html.escape(page)}",
            f"candidate {page}",
        )
        rows.append(
            f"<div class='gallery-row'><h3>{html.escape(page)}</h3>"
            f"<div class='pair'>{ref_cell}{cand_cell}</div></div>"
        )

    heading = (
        f"Best-overall trial <code>{html.escape(str(trial_id))}</code> "
        f"(reward {trial['reward']:.3f})"
    )
    return f"<p>{heading}</p>\n" + "\n".join(rows)


def _galleries_html(scores, job_dir, task_path):
    """Items 6-7 combined, or "" when the job has no renders to show."""
    if not _gallery_available(job_dir, task_path):
        return ""
    page_map = _load_page_map(task_path)
    metric = _per_metric_gallery_html(scores, job_dir, task_path, page_map)
    overall = _best_overall_gallery_html(scores, job_dir, task_path, page_map)
    return f"""
<h2>6. Per-metric best / worst (reference | best | worst)</h2>
{metric}

<h2>7. Best-overall attempt vs reference (all pages)</h2>
{overall}
"""


# --- HTML assembly (full report) ----------------------------------------------


def render_html(scores, job_dir=None, task_path=None):
    """Assemble the full self-contained ``report.html`` string.

    Items 1-5 (scores + plots) always render. Items 6-7 (the screenshot
    galleries) render only when ``job_dir`` has persisted ``verifier/renders/``
    and ``task_path`` carries the baked reference screenshots; otherwise they are
    omitted so a renders-less job still produces a report.
    """
    meta = scores["meta"]
    title = f"Model-eval report — {html.escape(str(meta.get('task_id')))}"

    dist_uri = plot_distributions(scores)
    means_uri = plot_per_term_means(scores)
    heatmap_uri = plot_page_term_heatmap(scores)

    galleries = (
        _galleries_html(scores, job_dir, task_path)
        if job_dir is not None else ""
    )

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
  .gallery-row {{ margin: 1rem 0 1.5rem; }}
  .gallery-row h3 {{ font-size: 1rem; margin: 0 0 0.4rem; }}
  .gallery-row h3 .rng {{ font-weight: 400; color: #666; font-size: 0.85rem; }}
  .triple, .pair {{ display: grid; gap: 0.8rem; }}
  .triple {{ grid-template-columns: repeat(3, 1fr); }}
  .pair {{ grid-template-columns: repeat(2, 1fr); }}
  figure {{ margin: 0; }}
  figure img {{ border: 1px solid #ddd; }}
  figcaption {{ font-size: 0.8rem; color: #555; margin-top: 0.25rem;
                font-variant-numeric: tabular-nums; }}
  .missing {{ border: 1px dashed #ccc; color: #999; padding: 1.5rem;
              text-align: center; font-size: 0.85rem; }}
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
{galleries}
</body></html>
"""


# --- entry point --------------------------------------------------------------


def _task_path(job_dir):
    """The task dir from the job's first-trial ``config.task.path`` (or ``None``).

    The grader's reference screenshots are baked under this task, and the same
    config is what the harvester reads for seed provenance — so the galleries
    point at the exact reference images the grader compared against.
    """
    config = agg._first_trial_config(Path(job_dir))
    path = (config.get("task") or {}).get("path")
    return Path(path) if path else None


def build_report(job_dir, out_dir):
    """Harvest the job and write scores.json + scores.csv + report.html."""
    job_dir = Path(job_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    scores = agg.harvest(job_dir)
    agg.write_scores(scores, out_dir)
    html_str = render_html(scores, job_dir=job_dir, task_path=_task_path(job_dir))
    (out_dir / "report.html").write_text(html_str)
    return out_dir


def _default_out(job_dir):
    return REPO / "reports" / "model-eval" / Path(job_dir).name


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("job_dir", help="saved Harbor job dir, e.g. jobs/opus47-004")
    parser.add_argument(
        "--out", default=None,
        help="output dir (default: reports/model-eval/<job-name>/)",
    )
    args = parser.parse_args(argv)

    out_dir = Path(args.out) if args.out else _default_out(args.job_dir)
    build_report(args.job_dir, out_dir)
    print(f"Report written to {out_dir}")


if __name__ == "__main__":
    main()
