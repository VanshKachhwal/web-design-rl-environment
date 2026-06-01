"""Build the per-task model-eval report for a Task-2 (animation) Harbor job.

Task-2 mirror of Task 1's ``scripts/report.py``, trimmed to the **five data
sections** (Task 1's items 1-5) — the screenshot/filmstrip galleries (Task 1's
items 6-7) are intentionally dropped: for animations they would mean 6 filmstrip
frames x ref/cand x every page x every trial, far too heavy to embed, and the
deliverable READMEs are hand-written anyway.

Sections (parity with Task 1, terms swapped for the animation grader's):

    1. Provenance header (task id, seed tuple, animation style, model, executor,
       trials, cost/tokens, wall-clock, filmstrip timestamps, date, commit).
    2. Per-trial score table + a summary row (median / mean +/- std / min / max).
    3. Reward distribution + per-term distributions.
    4. Per-term mean bars (+/- std).
    5. Per-page x per-term heatmap (mean across trials).

Terms are the animation page-reward terms ``static_design / motion /
animation_judge`` (Task 1's four static terms are preserved nested under each
page in ``scores.json`` for drill-down). Alongside the report it writes the
harvest contract ``scores.json`` + ``scores.csv``. Everything the report renders
reads only the normalized object from :mod:`aggregate_results_anim`.

This module is the **untested shell** (matplotlib + HTML/markdown assembly); the
data behind every table/plot is the unit-tested pure core in that harvester.

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

matplotlib.use("Agg")  # headless: no display, deterministic PNG output.
import matplotlib.pyplot as plt  # noqa: E402

from . import aggregate_results_anim as agg  # noqa: E402

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


def render_markdown(scores, out_dir):
    """Write ``report.md`` + sibling plot PNGs into ``out_dir`` (GitHub-native)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = scores["meta"]

    _fig_to_file(_fig_distributions(scores), out_dir / "distributions.png")
    _fig_to_file(_fig_per_term_means(scores), out_dir / "per_term_means.png")
    _fig_to_file(_fig_page_term_heatmap(scores), out_dir / "heatmap.png")

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
"""
    (out_dir / "report.md").write_text(md)
    return out_dir


# --- entry point --------------------------------------------------------------


def build_report(job_dir, out_dir, fmt="html"):
    """Harvest the job and write scores.json + scores.csv + the report.

    ``fmt`` is ``"html"`` (default, a self-contained ``report.html``) or
    ``"markdown"`` (a GitHub-renderable ``report.md`` + sibling plot PNGs). Both
    read only the normalized harvest from :mod:`aggregate_results_anim`.

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
        render_markdown(scores, out_dir)
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
                        help="self-contained 'html' (default) or GitHub 'markdown'.")
    args = parser.parse_args(argv)

    out_dir = Path(args.out) if args.out else _default_out(args.job_dir)
    build_report(args.job_dir, out_dir, fmt=args.format)
    print(f"Report written to {out_dir}")


if __name__ == "__main__":  # pragma: no cover
    main()
