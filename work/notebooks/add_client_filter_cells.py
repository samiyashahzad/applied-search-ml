"""
Adds investigation cells to w03_data_contract.ipynb:
  1. Check if CTE's missing date filter is the cause (scans all months vs just March)
  2. Check if any client has mixed TRUE/FALSE flags within the same month
  3. Groupby check for the all-zero pattern
"""

import json, uuid

NB_PATH = "w03_data_contract.ipynb"

# ── Cell 1: Investigation - CTE date filter ──────────────────────────────────
cte_date_cell = {
    "cell_type": "code",
    "execution_count": None,
    "id": str(uuid.uuid4())[:8],
    "metadata": {},
    "outputs": [],
    "source": [
        "# ── Investigation 1: Does the CTE's missing date filter explain 36 vs 43? ──\n",
        "#\n",
        "# The measurable_clients CTE has NO date filter:\n",
        "#   SELECT DISTINCT client_hash_id FROM {FACT_DAILY}\n",
        "#   WHERE client_has_ga4 IS TRUE AND client_has_gsc IS TRUE\n",
        "#\n",
        "# But the ANY_VALUE diagnostic query filtered to March only.\n",
        "# So the CTE might be pulling in clients from OTHER months\n",
        "# who had both flags TRUE in, say, February — but not in March.\n",
        "\n",
        "cte_no_date = f\"\"\"\n",
        "SELECT COUNT(DISTINCT client_hash_id) AS clients_no_date_filter\n",
        "FROM {FACT_DAILY}\n",
        "WHERE client_has_ga4 IS TRUE\n",
        "  AND client_has_gsc IS TRUE\n",
        "\"\"\"\n",
        "\n",
        "cte_with_date = f\"\"\"\n",
        "SELECT COUNT(DISTINCT client_hash_id) AS clients_march_only\n",
        "FROM {FACT_DAILY}\n",
        "WHERE client_has_ga4 IS TRUE\n",
        "  AND client_has_gsc IS TRUE\n",
        "  AND report_date >= '2026-03-01' AND report_date < '2026-04-01'\n",
        "\"\"\"\n",
        "\n",
        "print(\"CTE without date filter (all months):\")\n",
        "print(con.sql(cte_no_date).df())\n",
        "print()\n",
        "print(\"CTE with March date filter:\")\n",
        "print(con.sql(cte_with_date).df())\n",
    ],
}

# ── Cell 2: Investigation - mixed flags within a client ───────────────────────
mixed_flags_cell = {
    "cell_type": "code",
    "execution_count": None,
    "id": str(uuid.uuid4())[:8],
    "metadata": {},
    "outputs": [],
    "source": [
        "# ── Investigation 2: Do any clients have MIXED TRUE/FALSE flags? ──────\n",
        "#\n",
        "# If client_has_ga4 = TRUE on some rows and FALSE on others for the\n",
        "# same client in March, then:\n",
        "#   - DISTINCT (in the CTE): includes the client (at least one row matches)\n",
        "#   - ANY_VALUE (in the diagnostic): picks arbitrarily, might pick FALSE\n",
        "#\n",
        "# That would make the two queries disagree.\n",
        "\n",
        "mixed_check = f\"\"\"\n",
        "SELECT\n",
        "    client_hash_id,\n",
        "    COUNT(DISTINCT client_has_ga4) AS ga4_distinct_values,\n",
        "    COUNT(DISTINCT client_has_gsc) AS gsc_distinct_values,\n",
        "    MIN(client_has_ga4::INT)       AS ga4_min,\n",
        "    MAX(client_has_ga4::INT)       AS ga4_max,\n",
        "    MIN(client_has_gsc::INT)       AS gsc_min,\n",
        "    MAX(client_has_gsc::INT)       AS gsc_max\n",
        "FROM {FACT_DAILY}\n",
        "WHERE report_date >= '2026-03-01' AND report_date < '2026-04-01'\n",
        "GROUP BY client_hash_id\n",
        "HAVING COUNT(DISTINCT client_has_ga4) > 1\n",
        "    OR COUNT(DISTINCT client_has_gsc) > 1\n",
        "\"\"\"\n",
        "\n",
        "mixed_df = con.sql(mixed_check).df()\n",
        "print(f\"Clients with mixed flags in March: {len(mixed_df)}\")\n",
        "if len(mixed_df) > 0:\n",
        "    print()\n",
        "    print(mixed_df)\n",
        "else:\n",
        "    print(\"No clients have mixed flags -- the mismatch is NOT from mixed values.\")\n",
    ],
}

# ── Cell 3: All-zero pattern check ───────────────────────────────────────────
zeros_check_cell = {
    "cell_type": "code",
    "execution_count": None,
    "id": str(uuid.uuid4())[:8],
    "metadata": {},
    "outputs": [],
    "source": [
        "# ── Investigation 3: Are all-zero rows isolated to a few clients? ─────\n",
        "#\n",
        "# The head(10) showed all zeros from client_625b6439094e23e4.\n",
        "# Is that one low-activity client, or a widespread pattern?\n",
        "\n",
        "# Pages per client\n",
        "pages_per_client = monthly_features.groupby('client_hash_id').size().reset_index(name='page_count')\n",
        "print(\"Pages per client:\")\n",
        "print(pages_per_client.sort_values('page_count', ascending=False).to_string())\n",
        "print()\n",
        "\n",
        "# How many pages have ALL zeros across engagement columns?\n",
        "zero_engagement = monthly_features[\n",
        "    (monthly_features['total_sessions'] == 0) &\n",
        "    (monthly_features['total_engaged_sessions'] == 0) &\n",
        "    (monthly_features['total_pageviews'] == 0)\n",
        "]\n",
        "\n",
        "print(f\"Total pages in feature frame:     {len(monthly_features):,}\")\n",
        "print(f\"Pages with zero engagement:        {len(zero_engagement):,}\")\n",
        "print(f\"Pages with some engagement:        {len(monthly_features) - len(zero_engagement):,}\")\n",
        "print()\n",
        "\n",
        "# Which clients own the zero-engagement pages?\n",
        "zeros_by_client = zero_engagement.groupby('client_hash_id').size().reset_index(name='zero_pages')\n",
        "total_by_client = monthly_features.groupby('client_hash_id').size().reset_index(name='total_pages')\n",
        "client_summary = total_by_client.merge(zeros_by_client, on='client_hash_id', how='left')\n",
        "client_summary['zero_pages'] = client_summary['zero_pages'].fillna(0).astype(int)\n",
        "client_summary['zero_pct'] = (client_summary['zero_pages'] / client_summary['total_pages'] * 100).round(1)\n",
        "print(\"Zero-engagement pages by client:\")\n",
        "print(client_summary.sort_values('zero_pages', ascending=False).to_string(index=False))\n",
    ],
}

# ── Inject into notebook ─────────────────────────────────────────────────────
with open(NB_PATH, "r", encoding="utf-8") as f:
    nb = json.load(f)

nb["cells"].extend([cte_date_cell, mixed_flags_cell, zeros_check_cell])

with open(NB_PATH, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print("[OK] Added 3 investigation cells to w03_data_contract.ipynb:")
print("  1. CTE date filter check (all months vs March only)")
print("  2. Mixed TRUE/FALSE flags check per client")
print("  3. All-zero pattern check (which clients, how many pages)")
