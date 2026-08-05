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

## What is Next?

With Notebook 3 (`w03_data_contract.ipynb`) finally complete, I have a perfectly clean dataset and a deep understanding of the traps (Zero vs Null, Pipeline gaps, and Target Leakage). Now it's time to move into the modeling weeks!
