# Shared-loss relatedness, version 1

This experimental ranking complements binary Pearson correlation. It does not
change correlation clustering. Run it explicitly in the shared-loss panel;
metadata loads through the independent lane, and scoring runs in a Web Worker.
All groups participate, with the top 100 positive pairs retained for display.

For each group, assume one origin at the last common ancestor of its observed
presences. Traverse its descendants: every maximal all-absent clade is one loss
candidate. This Dollo-like construction avoids counting one ancestral absence
once per descendant species. Absences outside that origin are not evidence of
loss. Groups present in fewer than two tips provide no inferred loss events.
We require an exact branch match between two groups: overlapping but unequal
holes do not count as co-losses. BLAST-pending clades and undated loss edges are
excluded and their number reported. Other no-finding cells are treated as
absence, which can include annotation/detection failures.

For branch b and group g:

    t = branch length / maximum known root-to-tip path
    p(g,b) = 1 - exp(-h * r(g) * t)
    w(g,b) = -ln(clamp(p(g,b), 1e-6, 1-1e-6)) / descendant_tips(b)^alpha

Defaults: h = 0.1 per tree height, alpha = 0.5. Both are adjustable. r is the
release/group-validated OrthoDB evolutionary rate. Missing rates use 1 and the
number of measured rates is shown. Zero rates are retained; the probability
floor caps their contribution. Time units cancel in normalization; changing the
cohort/tree height can change rankings. A topological tree without lengths is
not scored.

For a pair, W is the sum of mean weights on exact shared loss branches, K is the
number of such branches, and T_g is the sum of all eligible loss weights for g:

    overlap = 2*W / (T_i + T_j)
    score = W * sqrt(K) * overlap

The shared branches are disjoint under each inferred history. The sqrt(K) bonus
explicitly favors repeated matches; overlap penalizes unshared losses. Smaller
clades and shorter branches contribute more. Size is sampled descendant-tip
count, not true clade diversity: sampling affects this score.

Sequence evolutionary rate is NOT a measured gene-loss hazard. Its linear
coupling to loss propensity and h are assumptions of this first heuristic, not
fitted biological parameters. Scores are neither p-values nor calibrated
posterior probabilities. Dollo-like reconstruction does not propagate ancestral
uncertainty or allow regain/HGT. Branch matches therefore do not prove historical
independence, causal coupling or significance. Lineage-specific background loss
propensity is not fitted in version 1. Future validation should compare known
functional links and simulated independent loss processes, assess sampling and
parameter sensitivity, and consider probabilistic gain/loss inference.

Scientific context:
- https://academic.oup.com/bioinformatics/article/23/1/14/189792
  (phylogenetic loss-event comparisons and constrained evolution models).
- https://pmc.ncbi.nlm.nih.gov/articles/PMC1802574/
  (gene-loss propensity estimated with branch lengths, distinct from sequence rate).
- https://pmc.ncbi.nlm.nih.gov/articles/PMC10995720/
  (limitations of Dollo ancestral reconstruction).

Implementation: public/loss-score.mjs (pure computation), loss-worker.mjs,
loss-ui.mjs. Focused tests: node --test web/tests/loss-score.test.mjs.
