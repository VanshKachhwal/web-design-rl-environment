# 21 — Seed sampler spans the full archetype×aesthetic grid (kill the diagonal collapse)

Status: done (committed edf9170)

## Parent

PRD: `.scratch/site-generator/PRD.md`. Builds directly on issue 02 (the
stratified sampler). Surfaced by the live 20-seed Modal batch, which produced
the **same** archetype+aesthetic site twice (`saas-landing` + `swiss-editorial`,
`local-service` + `luxury-serif`, …) — the diversity engine is collapsed.

## Background (the exact mechanism)

`sample_seeds` advances each stratified axis by a per-axis *coprime stride*:

```python
archetype = archetypes[(i * arch_stride) % len(archetypes)]
aesthetic = aesthetics[(i * aes_stride) % len(aesthetics)]
```

`ARCHETYPES` and `AESTHETICS` are **both length 10**, so `_coprime_stride(10)`
returns `7` for **both** axes → `arch_stride == aes_stride == 7`. The archetype
index therefore *always equals* the aesthetic index, and the `(archetype,
aesthetic)` pair walks a single diagonal of the 10×10 grid:

- **10 of 100** archetype×aesthetic pairs are reachable — at *any* batch size
  (90% of the design space is structurally unreachable).
- **30 of 300** archetype×aesthetic×complexity triples reachable.
- A 20-seed batch visits each of the 10 reachable pairs **twice** (seed `i` and
  `i+10`), differing only in complexity / audience / mood — e.g.
  `saas-landing`+`swiss-editorial` at indices 0 (low) and 10 (med).

**The obvious patch does not work.** Giving the two axes *different* coprime
strides (7 and 3) still yields only **10/100**: both indices are linear in
`i mod 10`, so the pair's period is `lcm(10, 10) = 10` for *any* stride pair. Two
equal-length linear sequences sharing one index can never produce more than 10
distinct pairs.

## What to build

Walk archetype×aesthetic as **one flattened product space** instead of two
locked diagonals, keeping the module fully deterministic (no RNG) and the public
interface (`sample_seeds`, `Seed`, `expand_seed`) unchanged.

- Treat the archetype×aesthetic grid as a single space of size
  `len(ARCHETYPES) * len(AESTHETICS)` and step it with **one stride coprime to
  that product size**, then decode the flattened index back to
  `(archetype_index, aesthetic_index)` (e.g. `j // L`, `j % L`). A stride coprime
  to the product makes a single additive walk a permutation of the whole grid, so
  **all 100 pairs are reachable** and no pair repeats until the batch exceeds the
  grid size. Pick the stride so short prefixes still spread across *both* axes
  (a prototype with stride `31` over a 100-cell grid gives the first 20 pairs all
  distinct, archetype cycling `0,3,6,9,2,5,8,1,4,7,…`, aesthetic `0..9`).
- Complexity, audience, and brand_mood stay independent deterministic steppers
  (their current `i % len` is fine — they are not the collapsed axes).
- Keep determinism structural: same `count` → identical list; any prefix of
  `sample_seeds(N)` is still a prefix of `sample_seeds(M>N)` if that property is
  retained (note: the existing prefix-stability already holds and is relied on by
  the `seed_id` index prefix — preserve it).
- The walk must generalize if an axis length changes (don't hard-code 10/100);
  derive `L` and the product size from the taxonomy tuples.

Scope is **only** the sampler's grid walk + its tests. Do not touch the
taxonomy vocabulary, `expand_seed`'s output shape, or any downstream stage.

## Acceptance criteria

- [ ] `sample_seeds(100)` yields **100 distinct** `(archetype, aesthetic)` pairs
      (full grid coverage), up from 10.
- [ ] No `(archetype, aesthetic)` pair repeats within any batch of size
      ≤ `len(ARCHETYPES) * len(AESTHETICS)`; specifically `sample_seeds(20)` has
      20 distinct pairs.
- [ ] Short-prefix spread is preserved: the first `len(ARCHETYPES)` seeds touch
      every archetype at least once, and the first `len(AESTHETICS)` seeds touch
      every aesthetic at least once (or as close as the strides allow — assert the
      distinct-count is ≥ a high threshold, not a brittle exact sequence).
- [ ] Determinism unchanged: same `count` → identical list; no `random` /
      unseeded RNG introduced.
- [ ] The walk is derived from the taxonomy tuple lengths (no hard-coded 10/100);
      a test that monkeypatches a different-length axis still produces a full,
      non-repeating product walk.
- [ ] `Seed`, `expand_seed`, and `seed_id` behavior are unchanged for a given
      `(seed, index)`; full suite green (clean `TMPDIR`, Docker render test
      excluded).

## Blocked by

- None. Independent of issue 22 (the httpx retry fix). Touches only
  `generate/seeds.py` (and possibly a small `taxonomy` helper) + their tests.
