# 03 — `content` term (Tesseract OCR + word-multiset F1)

Status: done

## Parent

PRD: `.scratch/grader-mvp/PRD.md`

## What to build

Add the `content` dimension — the independent anti-gaming anchor. Extract visible text from
both candidate and reference screenshots with Tesseract OCR (deterministic, no VLM
involvement), normalize (lowercase, collapse whitespace), and score as a **word-multiset
F1**: recall penalizes missing text, precision penalizes hallucinated text. Order-robust.
`content` joins the existing per-page terms and gains a `content` key in `reward.json`.

This term must stay fully independent of the `design_judge` VLM so it remains a real
cross-check.

## Acceptance criteria

- [ ] `content` is a [0,1] float dimension added to `reward.json` and `reward-details.json`.
- [ ] Identical visible text scores `content` ≈ 1.0; removing words lowers recall; injecting words lowers precision; an empty candidate scores ≈ 0.
- [ ] Implementation uses OCR only — no call into the VLM judge.
- [ ] Tests cover the `content` metric's external behavior (missing / hallucinated / empty cases).

## Blocked by

- Issue 01 (walking skeleton + aggregate contract).

## Comments

- **Done (2026-05-30).** Built in a parallel worktree (alongside issue 04), merged to main.
  `content()` = `pytesseract.image_to_string` on both images → lowercase + `\w+` tokenize
  (drops punctuation) → word-multiset F1 (precision=hallucinated, recall=missing). Edge
  conventions: both empty → 1.0, one empty → 0.0. Fixtures rendered with Arial TTF size 40;
  an OCR-legibility test guards them. `pytesseract` added to the `grade` extra.
- **Env gotcha (not a product bug):** under this sandboxed harness, Tesseract's temp files
  fail unless pytest runs with `TMPDIR=/tmp` from a `/tmp` cwd. A normal terminal / the
  Harbor verifier container (which `apt install`s tesseract) is unaffected.
