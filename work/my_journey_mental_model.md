# My ML Internship Journey & Mental Model
*(A casual, living document to help remember what I am doing and why)*

## The Ultimate Goal
I am building a **Content Action Playbook** (which will become my Capstone Research Paper). 
The goal is to build a Machine Learning model that tells the SEO team exactly which web pages they should spend their limited time fixing today.

---

## Where I Started (Phase 1: The Setup & The Idea)

### 1. The Starter Pipeline (Notebook 01 & 02)
*   **What I did:** I ran the starter code.
*   **Why I did it:** To prove my computer works, get a feel for the data, and see what a finished ML pipeline looks like before I had to build my own.

### 2. Picking the Problem (`w01_research_question.ipynb`)
*   **What I did:** I picked the **CTR / Engagement Opportunity Scoring** lane. I ran a quick pandas script that showed out of 30,000 pages, over 16,000 had good impressions (>500) but terrible clicks (<1% CTR). 
*   **Why I did it:** I proved mathematically that the SEO team has too many pages to look at manually. They need an automated, prioritized "Top 10" list every week. This notebook literally wrote the "Introduction" section of my final capstone paper.

### 3. The Math Translation (`w02_ml_task_framing.ipynb`)
*   **What I did:** I translated my SEO business problem into a Machine Learning problem. 
*   **Why I did it:** I decided this is a **Ranking** problem, not a Classification (Yes/No) problem. A simple rule like "Rank by CTR < 1%" is too dumb because it ignores search position and user engagement. I need an ML model to juggle all those signals at once.

---

## Where I Am Right Now (Phase 2: The Data Reality Check)

### 4. The Data Contract (`w03_data_contract.ipynb`)

**The Goal:** Before doing any Machine Learning, I have to prove the data I need actually exists and isn't garbage.

**What I've done so far:**
*   **The Rules:** I defined my rules in plain English. One row = one page, one day (source table). I aggregate to one page, one month (March 2026). I'm excluding tiny pages (<500 impressions) because they are too noisy.
*   **The Big Query Challenge:** I learned how to use DuckDB to connect to Hugging Face so I don't have to download 79 million rows to my laptop.

#### The 96% Drop — the first "wait, what?" moment

I ran my availability check with `IS TRUE` filters:

```sql
WHERE gsc_data_available IS TRUE
  AND ga4_data_available IS TRUE
```

Before filter: **9,841,378 rows**. After: **364,347 rows**. That's a 96% drop. My first reaction was "something's broken with the data pipeline."

But it wasn't broken. I just didn't understand what `ga4_data_available` actually means.

#### The Zero vs Null Thing — this clicked for me

Here's what was actually going on:

- **GSC tracks impressions** — a page can appear in search results even if nobody clicks it. So `gsc_data_available` is TRUE on lots of days, because search engines show your pages whether anyone visits or not.
- **GA4 tracks sessions** — it only fires when someone actually visits the page. Most pages on most days get zero visitors. That's not broken. That's just... most pages sitting quietly with no traffic.

So when I filtered `ga4_data_available IS TRUE`, I was saying "only keep days when someone actually visited." For a catalog of 519K pages, that throws away almost everything — because most page-days are naturally quiet.

The key insight: **a zero is real information, not missing data.** A page that gets 5,000 impressions and zero sessions is my strongest signal — that's exactly the kind of page my ranking should flag. But my filter was throwing those rows away before I could even count them.

#### Option C — the design decision

I worked through three options:

- **Option A:** Aggregate first, then check if the page had at least one GA4 day that month. Too conservative.
- **Option B:** Don't filter at all, just trust that SUM naturally handles zeros. Promising, but doesn't separate "real zero" from "no data pipe exists."
- **Option C (my pick):** Filter at the **client level**. Does this client have GA4 connected? If yes, keep all their daily rows, including real zeros. If no, exclude them entirely — their zeros are unmeasurable, not real.

The reasoning: a zero from a GA4-connected client means "nobody visited." A zero from a client without GA4 means "we can't observe anything." Same number, completely different meaning. That's the zero-vs-null distinction.

#### The CTE Approach — seemed right, wasn't

I built a CTE to get the list of "measurable clients":

```sql
WITH measurable_clients AS (
    SELECT DISTINCT client_hash_id
    FROM fact_daily
    WHERE client_has_ga4 IS TRUE
      AND client_has_gsc IS TRUE
)
```

Then JOINed against it. The idea was clean: get the client list once, join against it, aggregate everything.

But the numbers didn't add up.

#### Investigation Time — 36 vs 43

My earlier diagnostic (using `ANY_VALUE`) said 36 clients had both GA4 and GSC. But the JOIN produced 43 clients. An INNER JOIN can only keep or shrink — never grow beyond the filter. So something was wrong.

**Investigation 1: Missing date filter**

My CTE had no date filter! It scanned ALL 17 months of the warehouse. So a client that had both flags TRUE in, say, February but not March would still get included.

- Without date filter: **53 clients**
- With March filter: **43 clients**

Neither matched the original 36. So the missing date filter was part of the problem, but not all of it.

**Investigation 2: Mixed flags — the actually important discovery**

This one surprised me. I checked whether any client had mixed TRUE/FALSE values for `client_has_ga4` within the same month:

```sql
HAVING COUNT(DISTINCT client_has_ga4) > 1
```

**10 clients** had mixed values. `client_has_ga4` was TRUE on some March days and FALSE on others for the same client.

This directly contradicted what I assumed earlier — that `client_has_ga4` is a fixed fact about the client, constant for the whole month. It's not. These 10 clients probably connected or disconnected GA4 partway through March (onboarding mid-month, or an integration that broke).

This is why `ANY_VALUE()` was unreliable — it grabs one arbitrary row's value. For these mixed clients, it might grab a FALSE day and silently exclude a client that genuinely had GA4 on 20 other days. Roughly: 43 − 36 ≈ 7, close to the 10 mixed clients. The mechanism checks out.

**Investigation 3: The all-zero pattern**

My `head(10)` showed all-zero engagement rows, all from the same client. Looked alarming. But after grouping by client, the zero-engagement rates were spread across many clients at reasonable percentages (44%, 53%, 49%). Not one broken client — just the expected shape of the data. Most pages, most days, get zero engagement. Confirmed, not a new problem.

#### The Twist — two different kinds of flags

This is where it all came together. There are two types of columns in the data, and they need completely different treatment:

| Column | What it actually means | Filter it? |
|--------|----------------------|------------|
| `ga4_data_available` | "Did anyone visit this page today?" | **NO** — zero visits is real signal for my ranking |
| `client_has_ga4` | "Was GA4 connected on this day?" | **YES, row-level** — only sum days when the pipe existed |

Same logic for the GSC side:

| Column | What it actually means | Filter it? |
|--------|----------------------|------------|
| `gsc_data_available` | "Did this page get any impressions today?" | **NO** — zero impressions is real info |
| `client_has_gsc` | "Was GSC connected on this day?" | **YES, row-level** — only sum days when the pipe existed |

The `_data_available` flags are about **activity** (noisy, varies daily, zeros are normal). The `client_has_` flags are about **connectivity** (structural, rarely changes, but CAN change mid-month for some clients).

#### The Actual Fix

Drop the CTE. Drop the JOIN. Drop `ANY_VALUE`. Just put it in the WHERE clause:

```sql
SELECT
    content_hash_id,
    client_hash_id,
    SUM(gsc_impressions)        AS total_impressions,
    SUM(gsc_clicks)             AS total_clicks,
    AVG(gsc_avg_position)       AS average_position,
    SUM(ga4_sessions)           AS total_sessions,
    SUM(ga4_engaged_sessions)   AS total_engaged_sessions,
    SUM(ga4_pageviews)          AS total_pageviews
FROM fact_daily
WHERE report_date >= '2026-03-01' AND report_date < '2026-04-01'
  AND client_has_ga4 IS TRUE
  AND client_has_gsc IS TRUE
GROUP BY content_hash_id, client_hash_id
```

What's NOT there: `ga4_data_available IS TRUE`, `gsc_data_available IS TRUE` — because zeros from connected clients are real.

What IS there: `client_has_ga4 IS TRUE`, `client_has_gsc IS TRUE` — because days without a connection are truly unobservable.

For the 10 clients who connected mid-month, this correctly sums only the days they were actually connected. Honest partial month > wrong full month.

#### The Grain Didn't Change

Still one page, one month. The fix changed *how* I filter before aggregating, not *what* a row represents after aggregation. Adding `client_hash_id` to the GROUP BY just carries it through (a page belongs to exactly one client anyway).

---

## Lessons I'm Keeping

1. **Zero ≠ null.** A real zero is information. A null wearing a zero's clothes is missing data. They look identical in a SUM but mean completely different things.
2. **Where you filter matters.** Row-level before aggregation vs. after aggregation vs. client-level — same filter text, completely different results.
3. **"Client-level" isn't always constant.** I assumed `client_has_ga4` was a fixed property. Investigation proved 10 clients had it change mid-month. Don't assume — check.
4. **ANY_VALUE is dangerous for mixed data.** It picks arbitrarily. If the underlying values aren't actually constant, it silently gives you the wrong answer.
5. **A 96% drop isn't always a bug.** Sometimes it's just the honest shape of your data, and the real bug is your filter being too narrow for what you actually need.

---

### 5. Validating the Exclusion Rule & Defining Features

#### The 0 Impressions Investigation (Hypothesis A vs B)
After fixing the aggregation query, I noticed the first 10 rows all had `total_impressions = 0.0` from the exact same client. This raised two hypotheses:
- **Hypothesis A:** This is a genuinely low-traffic client with lots of pages that get zero visibility (expected shape of data, just an extreme example).
- **Hypothesis B:** There's still a bug (e.g., GSC filtering is broken).

I ran a zero-impressions diagnostic to check how many pages had 0 impressions and if they were isolated to one client. 
**The finding:** Roughly half the rows in the entire `monthly_features` dataset had `total_impressions = 0`, and these zeros were spread across many clients at expected percentages. This confirmed **Hypothesis A**: most pages across a large content catalog simply do not receive meaningful search traffic in any given month. Zero impressions is the normal case, not a bug.

#### Validating the 500-Impression Exclusion Rule
This finding was a massive win for my capstone. Earlier, I wrote a rule to exclude pages with `< 500 impressions` because they are "unreliable". Now I have hard evidence to back it up:
- Almost 50% of the dataset has exactly 0 impressions.
- Pages with zero or near-zero impressions produce a CTR of `0/0` (undefined) or wildly unstable ratios from tiny counts.
- The `< 500 impressions` cutoff isn't arbitrary—it statistically removes this unstable tail and focuses the model on pages where CTR and engagement are actually measurable.

#### Defining the 5 Features (and the Leakage Check)
I defined my five locked features. To prevent data leakage, every feature must be knowable **at the decision moment** (before an analyst decides to review a page).

| Feature | Available when? |
|---|---|
| `total_impressions` | Raw count of search appearances during March, recorded independently by GSC before any human reviews the page; cannot be influenced by a review decision that hasn't happened yet. |
| `total_clicks` | Same reasoning as impressions: a raw, already-settled count of March search behavior, recorded before any review occurs. |
| `ctr` | Computed entirely from March's impressions and clicks, both already-settled facts; does not depend on any future outcome or review action. |
| `average_position` | Google's measured ranking during March, fully settled by the time an analyst would review the page; not something that changes based on the review itself. |
| `total_engaged_sessions` | Recorded user behavior from March via GA4, same category as the others — independent of any review decision. |

*(Limitation to note in the report: GA4 data can arrive with more lag than GSC. While not a leakage issue for this retrospective analysis, it is a data-lag issue that should be flagged for real-time deployment).*

---

### 6. The Leakage Trap (How to cheat, and how to get caught)

**The Goal:** The assignment was to prove I understand Data Leakage by adding a cheating column, watching a simple model (Depth-2 Tree) hit an absurdly perfect score (0.98+), and then removing the cheat to show the honest score.

Here is the exact journey of how I failed twice before getting it right:

#### Attempt 1: The Overcomplicated Statistics
* **What I did:** I queried April CTR (future data) and ran a Spearman rank correlation against March CTR, plotting it on a scatter plot. 
* **Why it was wrong:** I completely ignored the assignment instructions. The assignment asked for a simple Decision Tree and a Precision@50 score jump. I went down a statistical rabbit hole instead.

#### Attempt 2: The Weak Leak (April CTR)
* **What I did:** I deleted the scatter plots, built the Depth-2 Decision Tree, and fed it `april_ctr` as the cheating column. 
* **What happened:** The model's score only jumped from `0.68` to `0.78`. 
* **Why it was wrong:** A 10-point jump is not "absurdly perfect." Why didn't it hit 0.98+? Because the real world is messy. April's search behavior (CTR) is highly correlated with March (~0.85), but it fluctuates. A tiny Depth-2 tree couldn't use fluctuating future data to perfectly predict March's opportunities. It was a leak, but a *weak* leak.

#### Attempt 3: The Realization — Target Leakage
* **The Critique:** I realized how I defined my label: `is_opportunity = (total_impressions >= median) AND (ctr <= median)`. 
* **The Fix:** My label was built using the March `ctr` column! If you want an absurd 0.98+ score jump, the ultimate cheat code isn't future data—it's giving the model the exact ingredient used to calculate the answer key. 
* **The Result:** I dropped `april_ctr` and fed the model the March `ctr` column. The tree instantly reverse-engineered my math formula (`if ctr <= median, predict 1`). The Precision@50 jumped perfectly to **`1.00`**. When I removed the `ctr` column, it dropped back to an honest **`0.74`**. 

#### The Lesson
Not all leaks are equally severe. Leaking a future, correlated metric might give your model a 10-point bump. But leaking a component of your own label (**Target Leakage**) guarantees a massive, perfectly absurd score because the model isn't learning anything—it's just copying your math homework. **Never use a feature that was used to mathematically calculate your label.**

---

### 7. The Danger of Averages (w04_baseline_score.ipynb)

**The Problem:** I'm building a baseline rule that flags pages as "underperforming" if their CTR falls below the average CTR of their position tier (e.g., positions 3-5). But I have to exclude low-impression pages before calculating that tier average. Why?

* **The Noise (Small Denominators):** A solid page with 30 clicks out of 2,000 impressions has a true, reliable CTR of **1.5%**. But a page with only 3 impressions might get 1 lucky click, resulting in a **33%** CTR. 
* **The Unweighted Average Trap:** If I just do a standard average (`.mean()`) across the tier, every page gets one equal vote. The noisy 3-impression page (33%) gets the exact same mathematical weight as the solid 2,000-impression page (1.5%). 
* **The Distortion:** Because these few noisy pages have massive CTRs compared to the true average, they mathematically distort the tier's average, artificially inflating it (e.g., pulling it from a true 1.5% up to a fake 2.2%).
* **The Business Impact:** If my rule flags pages that fall below a fake 2.2% baseline, it will accidentally flag perfectly healthy, normal pages (like the ones sitting at 1.5%) as "underperforming". I would end up wasting the SEO team's time chasing false positives. 

**The Fix:** Always filter out the noise (e.g., `< 500 impressions`) *before* taking the average, so the baseline reference point is built purely on solid, statistically reliable data.

---




### 8. Evaluating the Signals: The Messy Details (w04_baseline_score.ipynb)

Before building the final ranking queue, I had to statistically prove two hypotheses using bucket tables. I learned a ton of messy, real-world pandas details along the way.

#### Signal A: Search Position vs. CTR
* **The Hypothesis:** Search position strictly dictates what a "good" CTR is. A 0.5% CTR at Rank #1 is awful, but at Rank #50 it's a miracle. We can't use a single global threshold; we must judge pages against their peers.
* **The Messy Details (Categorical Traps):** I used `pd.cut` to bin the `average_position` into tiers (`top_3`, `page_1`, `striking`, `page_3_5`, `deep`). But I learned that `pd.cut` generates a strict `Categorical` type. When I tried to do `.fillna("no_data")`, pandas threw an error because "no_data" wasn't an officially defined bin! I had to learn to do `.cat.add_categories(["no_data"])` *first* before filling the NaNs. 
* **The Units Trap:** My table output `0.0039` for the Top 3 tier. I almost multiplied this by 100 to make it `0.39` for the rest of my math. **Huge mistake.** If you multiply a *percentage* (0.39) by impression volume, you artificially inflate your "missed clicks" by 100x! I learned to strictly display percentages for human readability, but **always use the raw fraction for math.**
* **The Verdict (CONFIRMED):** CTR declined monotonically with zero reversals: `top_3 (0.39%) -> page_1 (0.35%) -> striking (0.29%) -> page_3_5 (0.15%) -> deep (0.03%)`. This perfectly proved that search position drives CTR, justifying the decision to compare a page against its own tier average.

#### Signal B: Impression Volume vs. CTR
* **The Hypothesis:** CTR is roughly independent of impression volume. A page with high traffic isn't inherently more "clickable" than a page with low traffic. 
* **The Buckets:** I bucketed impressions into `moderate` (300+), `good` (3,000+), and `excellent` (30,000+). Since I already filtered out pages with < 500 impressions, I didn't need to worry about "no_data" or "low" tiers.
* **The Verdict (CONFIRMED):** The CTR stayed completely flat across the tiers: `moderate (0.29%) -> good (0.30%) -> excellent (0.25%)`. Unlike Signal A's massive 10x drop, Signal B didn't trend anywhere. This proved that impression volume is *not* a signal of CTR quality. Instead, impression volume should only be used as a **multiplier** to prioritize which broken pages to fix first!


### 9. The Baseline Queue & The Human Element (w04_baseline_score.ipynb)

**The Goal:** Build the actual rule that flags underperforming pages, score them so human reviewers know which ones to fix first, and then manually review the top 20 to see where the math fails in the real world.

#### The Volume Filter Trap (Section 1)
* **What I almost did:** I almost wrote a rule saying, "Only flag pages if they are in the 'Good' or 'Excellent' impression tiers (>3000 impressions)."
* **Why it was wrong:** By hard-filtering the population, I would have made my model literally blind to 69% of the dataset (the 'Moderate' tier). Even if a moderate-tier page had a screamingly massive CTR gap, the model would never look at it.
* **The Fix:** Don't *filter* by volume, **rank** by volume. I apply the rule to *all* reliable pages (>=500 impressions), calculate the gap, and then multiply that gap by the volume to get `missed_clicks`. High volume pages naturally float to the top, but moderate pages aren't artificially ignored.

#### The "Bouncer" Condition (Section 2)
* **The Problem:** If you just rank by `missed_clicks` without a minimum threshold, a page with 1 million impressions and a tiny, insignificant 0.01% CTR gap will generate a huge `missed_clicks` score and shoot to the top of the queue. That page is perfectly healthy, just highly trafficked.
* **The Fix:** I added a "Bouncer" condition: `ctr < (tier_avg_ctr / 2)`. The Bouncer says: "I don't care how much traffic you have, if your CTR isn't at least 50% worse than your peers, you aren't broken, so you don't even get on the list." Only the broken pages get ranked.

#### The Top 20 Review & Real-World Doubts (Section 3 & 4)
Math is perfect, but the real world (and Google search) is messy. When I manually reviewed the Top 20 results, I realized the math can't see the context of the search page. I found three massive reasons why a "SEVERE_CTR_GAP" might actually be a False Positive:
1. **Zero-Click SERP:** If a page has 118,000 impressions in the Top 3 but literally 0 clicks, it's not a bad title tag. It's mathematically impossible for text. It's almost certainly a Google Instant Answer (like a calculator) or an Image Carousel where users get the answer without clicking.
2. **Branded Search:** A page ranking #2 with huge impressions but low clicks might just be ranking for a competitor's brand name. Users see our link but only want the official competitor site.
3. **Seasonality:** A page might spike in impressions but have terrible CTR because the content's title is out-of-date for the current season (e.g. says "2025" when users want "2026").

**The ML Lesson:** My simple baseline rule assigns one global reason code (`SEVERE_CTR_GAP`) to everything. But a human can instantly spot the difference between a Zero-Click SERP and a Legitimately Broken Title. This proves why we eventually need a true ML model: to learn these nuanced differences and assign sharper, more granular reason codes (like `SEVERE_CTR_GAP_SUSPECTED_ZERO_CLICK`) to save human reviewers even more time.

## Phase 3: The ML Modeling Lane (w05_model.ipynb)

**The Goal:** Build a Machine Learning model (Linear Regression first, then Random Forest) to predict April `missed_clicks` using only March features, and see if it can capture more total missed clicks than my W04 baseline heuristic.

### 1. Taming the Whales (Log Transforms)
*   **The Problem:** The `missed_clicks` target is heavily skewed (heavy-tailed). A few "whale" pages have 800+ missed clicks, while typical pages have under 5. Because Linear Regression minimizes *squared* error, it will completely abandon the normal pages and bend its entire math formula to fit the whales.
*   **The Fix:** I used `np.log1p()` on the target and the massive volume features (`total_impressions_march`, `clicks`, `sessions`). The log transform violently shrinks massive gaps (a gap of 45,000 shrinks to ~1.0) while leaving small gaps relatively spread out. 
*   **The Nuance:** I did *not* log transform `ctr_march` or `average_position_march` because they are naturally bounded (0-1 and 1-100+) and are not heavy-tailed.
*   **The Gotcha:** You have to remember to un-log the predictions using `np.expm1()` immediately after `model.predict()`! If you sum up log-space predictions to report Business Value, you get a mathematically meaningless number.

### 2. The Group Shuffle Split (Avoiding Memorization)
*   **The Leakage Trap:** If I did a random `train_test_split`, pages from Client A would land in both the training set and the test set. The model would just memorize Client A's specific website structure (e.g., they have high CTR on "/blog/" pages) and cheat on the test set. 
*   **The Fix:** I used `GroupShuffleSplit` on `client_hash_id`. If Client A goes to the training set, ALL their pages go to the training set. The test set only sees brand new clients, simulating the real-world deployment of the model.
*   **The Lumpy Reality:** I set `test_size=0.25` expecting ~11 clients in the test set. I got 8. Why? Because the data is so lumpy (one client had 31,000 pages), the splitter hit its row-count threshold early. 

### 3. The Evaluation (The Grader)
To evaluate the model fairly, I had to sort the test set by what the *model* predicted was best, but grade it against what *actually* happened in April. I used two metrics on the Top 50 recommendations:
1.  **Precision@50:** Did the top 50 actually meet the W04 rule in April? (Target vs. Base Rate of random guessing).
2.  **Total Captured Clicks:** The sum of actual April missed clicks caught in the Top 50 net (The Ultimate Business Value).

### 4. The Sensitivity Check & The Grand Finale Verdict

I ran the evaluation on three models: The W04 Baseline Heuristic, Linear Regression (LR), and Random Forest (RF).

*   **The Scoreboard:**
    *   **Baseline:** 94% Precision@50 | 2,131 Captured Clicks
    *   **Linear Regression:** 96% Precision@50 | 1,274 Captured Clicks
    *   **Random Forest:** 86% Precision@50 | 1,698 Captured Clicks

*   **Wait, the Baseline won?** Yes! The ML models completely failed to beat the simple SQL rule from W04. 
*   **Why did LR fail?** While the log-transform stabilized the model, it made it too conservative. It prioritized "safe" medium opportunities instead of aggressively hunting the whales like the Baseline did.
*   **Why did RF fail?** Machine Learning models look for hidden, complex patterns. But our target (`missed_clicks`) is literally a strict algebraic formula: `CTR Gap * Volume`. You can't beat a perfect algebraic representation by throwing a black box at it.
*   **The Client Concentration Caveat:** 78% (39 out of 50) of the model's top predictions came from a single client. The test set was highly concentrated, so these results are directional. A true `GroupKFold` cross-validation would be needed to prove it works evenly across all clients.
*   **The Sensitivity Check:** I retrained the LR model without `log_impressions` and `log_clicks`. The model completely crashed, capturing only 179 clicks (losing 1,096 clicks of value). This connects directly back to my multicollinearity finding: my five features aren't five independent signals. Volume and CTR-related columns are highly entangled, and once you strip volume out, there's not much genuinely independent SEO signal left in what remains. The model's signal is almost entirely volume-driven; `ctr_march`, `log_engaged_sessions_march`, and `average_position_march` alone carry very little predictive power for which pages will have big April opportunities.
*   **The Exciting Conclusion & Final Verdict:** It feels anti-climactic that the "fancy AI" lost, but this is a massive win. A sensitivity check confirmed the model's signal is almost entirely volume-driven — removing impression/click features collapsed captured value by 86% (1,274 → 179 clicks for LR) — meaning the model has not found independent SEO insight beyond 'big pages stay big,' which is consistent with the baseline's simpler, volume-weighted approach already capturing most of the real signal. Because the problem is fundamentally algebraic (CTR Gap × Volume), the Baseline heuristic remains the recommended production system—it is more performant, perfectly interpretable, and requires zero ML infrastructure. That is exactly what a Senior Data Scientist is supposed to do: save the company money by finding the simplest, most effective solution.

## What is Next?
Wrapping up the final reporting and cleaning up the repository for submission!