"""
Plot AFP case counts from the epi_africa dataset for Nigeria, 2017–present.

Run with the VS Code play button or from the repo root:

    python scripts/sandbox/explore_epi_data.py
"""

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

from laser_polio_nigeria import _load_dotenv
_load_dotenv(REPO_ROOT / ".env")

from laser_polio.manifest_loader import load_manifest

manifest = load_manifest()

# ── Load and filter ────────────────────────────────────────────────────────────

epi = pd.read_hdf(manifest.epi, key="epi")
epi["date"] = pd.to_datetime(epi["month_start"])
epi["adm0"] = epi["dot_name"].str.split(":").str[1]

nga = epi[
    epi["dot_name"].str.startswith("AFRO:NIGERIA:")
    & (epi["date"] >= "2017-01-01")
].copy()

# Extract state (adm1) from dot_name: AFRO:NIGERIA:<STATE>:<LGA>
dot_parts = nga["dot_name"].str.split(":", expand=True)
nga["state"] = dot_parts[2]

# ── Sanity check: monthly cases by country ────────────────────────────────────

by_country = (
    epi[epi["date"] >= "2017-01-01"]
    .groupby(["date", "adm0"])["cases"].sum()
    .reset_index()
)
top_countries = (
    by_country.groupby("adm0")["cases"].sum()
    .sort_values(ascending=False).head(10).index.tolist()
)
pivot_countries = by_country[by_country["adm0"].isin(top_countries)].pivot_table(
    index="date", columns="adm0", values="cases", fill_value=0
)
pivot_countries = pivot_countries[pivot_countries.sum().sort_values(ascending=False).index]

fig_sanity, ax_s = plt.subplots(figsize=(14, 5))
pivot_countries.plot.bar(ax=ax_s, stacked=True, width=0.8, colormap="tab10", legend=True)
ax_s.set_title("Sanity check: Monthly AFP Cases by Country — Top 10 (2017–present)", fontsize=13, fontweight="bold")
ax_s.set_ylabel("Cases")
ax_s.set_xlabel("Month")
ax_s.legend(loc="upper left", ncol=2, fontsize=8, framealpha=0.8)
ax_s.grid(True, axis="y", alpha=0.3, linestyle="--")
ax_s.spines["top"].set_visible(False)
ax_s.spines["right"].set_visible(False)
jan_pos = [i for i, d in enumerate(pivot_countries.index) if d.month == 1]
ax_s.set_xticks(jan_pos)
ax_s.set_xticklabels([str(pivot_countries.index[i].year) for i in jan_pos], rotation=0, ha="center", fontsize=9)
plt.tight_layout()
sanity_path = REPO_ROOT / "results" / "epi_sanity_by_country.png"

totals = (
    epi[epi["date"] >= "2017-01-01"]
    .groupby("adm0")["cases"].sum()
    .sort_values(ascending=False)
    .astype(int)
)
print("\nTotal cases by country (2017–present):")
print(totals.to_string())

plt.savefig(sanity_path, dpi=150, bbox_inches="tight")
print(f"Saved: {sanity_path}")
plt.show()

# ── Aggregate (Nigeria) ───────────────────────────────────────────────────────

national = nga.groupby("date")["cases"].sum().reset_index()
by_state = nga.groupby(["date", "state"])["cases"].sum().reset_index()
top_states = (
    by_state.groupby("state")["cases"].sum().sort_values(ascending=False).head(10).index.tolist()
)

# ── Plot ───────────────────────────────────────────────────────────────────────

fig, axes = plt.subplots(2, 1, figsize=(14, 10))

# --- Panel 1: national monthly ---
ax = axes[0]
ax.bar(national["date"], national["cases"], width=25, color="steelblue", alpha=0.8)
ax.set_title("Nigeria: AFP Cases per Month (National Total, 2017–present)", fontsize=13, fontweight="bold")
ax.set_xlabel("Month")
ax.set_ylabel("Cases")
ax.set_xlim(pd.Timestamp("2017-01-01"), None)
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.grid(True, axis="y", alpha=0.3, linestyle="--")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

total = int(national["cases"].sum())
peak_row = national.loc[national["cases"].idxmax()]
ax.annotate(
    f"Peak: {int(peak_row['cases'])} ({peak_row['date'].strftime('%b %Y')})\nTotal: {total}",
    xy=(peak_row["date"], peak_row["cases"]),
    xytext=(30, 10),
    textcoords="offset points",
    fontsize=9,
    arrowprops=dict(arrowstyle="->", color="grey"),
)

# --- Panel 2: top 10 states stacked bar ---
ax = axes[1]
pivot = by_state[by_state["state"].isin(top_states)].pivot_table(
    index="date", columns="state", values="cases", fill_value=0
)
pivot = pivot[pivot.sum().sort_values(ascending=False).index]

pivot.plot.bar(ax=ax, stacked=True, width=0.8, colormap="tab10", legend=True)
ax.set_title("Nigeria: AFP Cases per Month by State — Top 10 States (2017–present)", fontsize=13, fontweight="bold")
ax.set_xlabel("Month")
ax.set_ylabel("Cases")
ax.legend(loc="upper left", ncol=2, fontsize=8, framealpha=0.8)
ax.grid(True, axis="y", alpha=0.3, linestyle="--")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

jan_pos = [i for i, d in enumerate(pivot.index) if d.month == 1]
ax.set_xticks(jan_pos)
ax.set_xticklabels([str(pivot.index[i].year) for i in jan_pos], rotation=0, ha="center", fontsize=9)

plt.tight_layout()
out_path = REPO_ROOT / "results" / "epi_nigeria_2017_present.png"
out_path.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(out_path, dpi=150, bbox_inches="tight")
print(f"Saved: {out_path}")
plt.show()
