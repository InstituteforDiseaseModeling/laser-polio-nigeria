"""
Tally VDPV2 cases from the AFP linelist for Kano state vs. all of Nigeria
over the last 5 and 10 years, and plot cases over time with Kano's share.

Run from the repo root:

    python scripts/sandbox/tally_vdpv2_kano.py

Requires the polio-immunity-mapping repo cloned alongside this one:
    ../polio-immunity-mapping/scn/cvd2/results/linelist_afp.csv
"""

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LINELIST_PATH = REPO_ROOT.parent / "polio-immunity-mapping" / "scn" / "cvd2" / "results" / "linelist_afp.csv"

TODAY = pd.Timestamp.now().normalize()
CUTOFFS = {
    "5 years": TODAY - pd.DateOffset(years=5),
    "10 years": TODAY - pd.DateOffset(years=10),
}

# ── Load ───────────────────────────────────────────────────────────────────────

df = pd.read_csv(LINELIST_PATH, low_memory=False, parse_dates=["donset"])

# Filter to VDPV2 cases only
vdpv2 = df[df["polio_virus_types"].str.contains("VDPV2", na=False)].copy()
vdpv2 = vdpv2.dropna(subset=["donset"])

nga = vdpv2[vdpv2["adm0_name"] == "NIGERIA"]
kano = vdpv2[(vdpv2["adm0_name"] == "NIGERIA") & (vdpv2["adm1_name"] == "KANO")]

# ── Tally ──────────────────────────────────────────────────────────────────────

print(f"VDPV2 case tallies (as of {TODAY.date()})\n")
print(f"{'Window':<12}  {'Kano':>6}  {'Nigeria':>8}  {'Kano share':>10}")
print("-" * 42)

for label, cutoff in CUTOFFS.items():
    n_kano = int((kano["donset"] >= cutoff).sum())
    n_nga = int((nga["donset"] >= cutoff).sum())
    share = n_kano / n_nga * 100 if n_nga > 0 else 0.0
    print(f"{label:<12}  {n_kano:>6}  {n_nga:>8}  {share:>9.1f}%")

# ── Yearly breakdown ───────────────────────────────────────────────────────────

print("\nYearly breakdown (Nigeria vs. Kano):\n")
print(f"{'Year':<6}  {'Kano':>6}  {'Nigeria':>8}  {'Kano share':>10}")
print("-" * 36)

nga_yr = nga.copy()
nga_yr["year"] = nga_yr["donset"].dt.year
kano_yr = kano.copy()
kano_yr["year"] = kano_yr["donset"].dt.year

cutoff_10y = TODAY - pd.DateOffset(years=10)
years = sorted(nga_yr[nga_yr["donset"] >= cutoff_10y]["year"].unique())

for yr in years:
    n_kano = int((kano_yr["year"] == yr).sum())
    n_nga = int((nga_yr["year"] == yr).sum())
    share = n_kano / n_nga * 100 if n_nga > 0 else 0.0
    print(f"{yr:<6}  {n_kano:>6}  {n_nga:>8}  {share:>9.1f}%")

# ── Monthly time series ────────────────────────────────────────────────────────

def to_month(series):
    return series.dt.to_period("M").dt.to_timestamp()

nga_m = nga.copy()
nga_m["month"] = to_month(nga_m["donset"])
kano_m = kano.copy()
kano_m["month"] = to_month(kano_m["donset"])

nga_monthly = nga_m.groupby("month").size().rename("nga")
kano_monthly = kano_m.groupby("month").size().rename("kano")

monthly = pd.concat([nga_monthly, kano_monthly], axis=1).fillna(0)
monthly.index = pd.to_datetime(monthly.index)
monthly = monthly[monthly.index <= TODAY]
monthly["share_pct"] = monthly["kano"] / monthly["nga"].replace(0, float("nan")) * 100

# ── Plot ───────────────────────────────────────────────────────────────────────

fig, ax1 = plt.subplots(figsize=(14, 5))

bar_width = 20  # days

ax1.bar(monthly.index, monthly["nga"], width=bar_width, color="#b0c4de", alpha=0.85, label="Nigeria (all states)")
ax1.bar(monthly.index, monthly["kano"], width=bar_width, color="#2171b5", alpha=0.95, label="Kano")
ax1.set_ylabel("VDPV2 cases per month", fontsize=11)
ax1.set_xlabel("")
ax1.spines["top"].set_visible(False)
ax1.tick_params(axis="y", labelcolor="#2171b5")

ax2 = ax1.twinx()
ax2.plot(
    monthly.index,
    monthly["share_pct"],
    color="#d62728",
    linewidth=1.8,
    marker="o",
    markersize=4,
    label="Kano share (%)",
    zorder=5,
)
ax2.set_ylabel("Kano share of Nigeria VDPV2 (%)", fontsize=11, color="#d62728")
ax2.tick_params(axis="y", labelcolor="#d62728")
ax2.set_ylim(0, 110)
ax2.spines["top"].set_visible(False)

ax1.xaxis.set_major_locator(mdates.YearLocator())
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax1.set_xlim(monthly.index.min() - pd.DateOffset(months=1), TODAY + pd.DateOffset(months=1))

lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=9, framealpha=0.8)

ax1.set_title("VDPV2 Cases Over Time: Kano vs. Nigeria (AFP linelist)", fontsize=13, fontweight="bold")
ax1.grid(True, axis="y", alpha=0.25, linestyle="--")

plt.tight_layout()
out_path = REPO_ROOT / "results" / "vdpv2_kano_vs_nigeria.png"
out_path.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(out_path, dpi=150, bbox_inches="tight")
print(f"\nSaved: {out_path}")
plt.show()
