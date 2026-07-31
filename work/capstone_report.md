# Capstone Report — CTR / Engagement Opportunity Scoring

- **Author:** Sophie
- **Lane:** CTR / Engagement Opportunity Scoring
- **Repo:** applied-search-ml
- **Date:** 2026-07-31

> The eight sections mirror the Pass / Needs-Work rubric axes, so nothing here is optional.

## 1. Problem framing

**Research Question:** Which pages should an SEO team review first because they appear to underperform in clicks or engagement relative to their visibility?

**Decision:** Given limited time, which pages should the SEO team review this week?

**Unit of Analysis:** A single web page.

**Output:** An Opportunity Score and a ranked list of pages with reason codes explaining why each page received its score.

**Action:** A human reviewer investigates the highest-ranked pages and decides whether to:
- improve titles or meta descriptions
- refresh content
- improve content quality
- improve user engagement
- monitor the page instead of changing it

**Cost of a wrong call:** 
- *False Positive:* The model ranks a page very highly even though it isn't actually worth reviewing, resulting in the SEO team wasting time.
- *False Negative:* A valuable page with genuine opportunity isn't recommended, meaning the business misses additional traffic or engagement because the page was never reviewed.

**Why data/ML helps here:** The relationship between impressions, CTR, position, freshness, engagement, and content characteristics is more complex than a single rule. A machine learning ranking model may identify useful combinations of signals that help prioritize review candidates more effectively than a fixed scoring rule. The goal is to improve prioritization rather than automate SEO decisions.

## 2. Data safety

Which data you used and which columns you deliberately excluded (and why). Leakage risks you
considered — especially label-derived fields (`trend_direction`, `trend_pct`) and pseudonymous
IDs (grouping only, never features). Confirm nothing client-identifying appears anywhere in
`work/`.

## 3. Baseline

The transparent rule or score you built first. Why it's a fair comparison, and its numbers on
the same data and metric as your model.

## 4. Model / analysis

Your method and why it fits the lane. The exact feature list (and what you left out on
purpose). The target or proxy definition, in one sentence.

## 5. Evaluation

Your split (grouped by client? time-aware?) and why. Metrics, model vs baseline **on the same
split**. What the errors look like — a short error analysis beats a big metric table.

## 6. Interpretation

What the model/clusters actually found. Feature importances or cluster profiles in plain
words. Surprises and negative results — a well-understood "no effect" is a valid result.

## 7. Recommendation

The ranked actions or decisions your output supports, and how a FlyRank editor would use them
tomorrow. State your confidence and the limits explicitly.

## 8. Reproducibility

The exact commands to re-run everything from a fresh clone, your random seeds, and your
environment (`pip freeze` highlights or `requirements.txt` deltas).

---

> **Claims checklist before submitting:** observed / measured / directional / decision-support
> **Metrics vs. base rate:** report your task's base rate (majority-class %) next to any
> precision@K or accuracy — a high score can just be a high base rate. AUC / lift over
> baseline are the honest discrimination numbers.
> language everywhere · no causal claims without an experiment or causal design · no
> "predicted Google's algorithm" · no client-identifying details · numbers in this report
> match a fresh re-run.
