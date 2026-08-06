# Capstone Report — CTR / Engagement Opportunity Scoring

- **Author:** Samiya Shahzad Malik
- **Lane:** CTR / Engagement Opportunity Scoring
- **Repo:** applied-search-ml
- **Date:** 2026-07-31

> The eight sections mirror the Pass / Needs-Work rubric axes, so nothing here is optional.

## 1. Problem framing

**Research Question:** Which pages should an SEO team review first because they appear to underperform in clicks or engagement relative to their visibility?

**Decision:** Given limited time, which pages should the SEO team review this week?

**Unit of Analysis:** A single web page.

**Output:** A ranked review queue, where each page receives an Opportunity Score together with one or more reason codes explaining why it was prioritized.

**Action:** A human reviewer investigates the highest-ranked pages and decides whether to:
- improve titles or meta descriptions
- refresh content
- review content quality
- improve user engagement
- monitor the page instead of changing it

**Cost of a wrong call:** 
- *False Positive:* The model ranks a page very highly even though it isn't actually worth reviewing, resulting in the SEO team wasting time.
- *False Negative:* A valuable page with genuine opportunity isn't recommended, meaning the business misses additional traffic or engagement because the page was never reviewed.

**Why data/ML helps here:** The relationship between impressions, CTR, position, freshness, engagement, and content characteristics is more complex than a single rule. A machine learning ranking model may identify useful combinations of signals that help prioritize review candidates more effectively than a fixed scoring rule. The goal is to improve prioritization rather than automate SEO decisions.

**Why this problem matters:** Because SEO teams often manage thousands of pages, reviewing every page is unrealistic. A ranked opportunity queue allows analysts to focus their limited effort on the pages that may produce the greatest benefit if investigated, while leaving lower-priority pages for later review.

## 2. Data safety

**Data Used and Excluded:** 
The dataset consists of daily performance records from GSC and GA4, aggregated to the monthly level (`content_hash_id`). We deliberately exclude pages with fewer than 500 monthly impressions. Our exploratory data analysis revealed that nearly 50% of pages naturally receive zero or near-zero impressions, which results in undefined (`0/0`) or wildly unstable CTRs. Excluding this long tail of low-traffic pages focuses the model on reliable, measurable signals.

**Leakage Risks Assessed:**
During testing, we investigated two distinct types of data leakage with very different severities. First, we tested a **"soft," real-world-plausible leak** by including future data (April CTR); because future CTR correlates strongly but imperfectly with past CTR, it provided a moderate, unrealistic bump to model performance. Second, we tested a **"hard," formulaic leak (Target Leakage)** by including March's own `ctr` column as a feature, even though `ctr` was used mathematically to define the `is_opportunity` proxy label. This hard leak allowed the model to simply reverse-engineer the label's formula, instantly inflating Precision@50 to an artificial `1.00`. Consequently, we strictly guard against both future-peeking and label-derived fields to ensure the model learns honest, generalized patterns.

**Identifiers and Privacy:**
Pseudonymous keys such as `content_hash_id` and `client_hash_id` are used exclusively for grouping and joining data. They are never provided to the model as features. We confirm that no client-identifying details (e.g., raw URLs, real client names) appear anywhere in the `work/` directory.

## 3. Baseline

**Baseline:** Rank pages with CTR below 1% by descending impressions.
*(Numbers will be added once the baseline model is run on the same data and metric as the ML model).*

## 4. Model / analysis

**ML Task Type:** Ranking (with an opportunity score)

**Target Proxy:** An initial proxy for review opportunity combines high search visibility (>1000 impressions), relatively low CTR (<1.0%), and low engagement (<5%).

*(Exact method and feature list to be finalized).*

## 5. Evaluation

**Metric:** The success of the ranking system will be evaluated using ranking-oriented metrics such as **Precision@K** or similar top-K evaluation, since the objective is to recommend the most valuable pages for review rather than classify every page correctly.

*(Splits and error analysis to be finalized after modeling).*

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
