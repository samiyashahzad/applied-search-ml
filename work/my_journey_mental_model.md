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

### 4. The Data Contract (`w03_data_contract.ipynb` - Currently working on this)
*   **The Goal:** Before doing any Machine Learning, I have to prove the data I need actually exists and isn't garbage. 
*   **What I've done so far:**
    *   **The Rules:** I defined my rules in plain English. One row = one page. I'm testing on March 2026. I'm excluding tiny pages (<500 impressions) because they are too noisy.
    *   **The Big Query Challenge:** I learned how to use DuckDB to connect to Hugging Face so I don't have to download 79 million rows to my laptop. 
    *   **The Big Design Decision:** I ran diagnostic queries and discovered something crazy: out of 9.8 million daily rows, only 364,000 rows had *both* Search Console (CTR) and Google Analytics (Engagement) data. Over 60% of the clients in the database don't track engagement!
    *   **The Choice:** I made the executive decision to throw away those 9.4 million rows. Why? Because a page with high CTR but 0% engagement is "clickbait," and I can't detect clickbait without GA4 data. 364k rows across 41 clients is still a massive dataset, and the quality of the data is much higher.

---

## What is Next? (How to finish this week)

To finish Notebook 3 (`w03_data_contract.ipynb`), I just have two small things left:

1.  **Build 5 Features:** I need to write a pandas/SQL cell that takes those 364k surviving rows and calculates max 5 features for my model (e.g., `ctr = clicks / impressions`). 
2.  **The Leakage Trap:** I have to purposely build a "cheating" feature (like using next month's clicks to predict this month's rank), watch my model score jump to 100%, and then delete it to prove I understand how data leakage ruins models.

*Once this notebook is done, I will have a perfectly clean dataset ready to feed into a real Machine Learning algorithm in Week 5!*
