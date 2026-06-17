import geopandas as gpd
import pandas as pd
pd.set_option("display.max_columns", None)

# AFP case linelist from the polio-immunity-mapping repo:
# https://github.com/InstituteforDiseaseModeling/polio-immunity-mapping
# File: scn/cvd2/results/linelist_afp.csv
# Expected to be cloned alongside this repo (i.e. ../polio-immunity-mapping/)
linelist_path = "../polio-immunity-mapping/scn/cvd2/results/linelist_afp.csv"
df = pd.read_csv(linelist_path, low_memory=False, parse_dates=["donset"])
shp = gpd.read_file(filename="data_local/curated/shp_africa_low_res.gpkg", layer="adm2")

# Filter to VDPV2 cases
df = df[df["polio_virus_types"].str.contains("VDPV2", na=False)]

# Drop rows with missing onset date
df = df.dropna(subset=["donset"])

# Create month_start from date of onset, floored to first of month
df["month_start"] = df["donset"].dt.strftime("%Y-%m-01")

# Aggregate AFP case counts per (guid, adm0_name, month_start)
cases = df.groupby(["guid", "adm0_name", "month_start"]).size().reset_index(name="cases")
cases["cases"] = cases["cases"].astype(float)

# Merge with shapefile to get dot_name
cases = cases.merge(shp[["guid", "dot_name"]], on="guid", how="left")

# Warn about districts not in the shapefile (e.g. non-Africa regions like EMRO)
unmatched = cases[cases["dot_name"].isna()]
if not unmatched.empty:
    n_districts = unmatched["guid"].nunique()
    n_rows = len(unmatched)
    total_cases = int(unmatched["cases"].sum())
    print(f"\nWARNING: {n_districts} districts ({n_rows} district-month rows, {total_cases} cases) not matched in shapefile.")
    counts_by_adm0 = (
        unmatched.groupby("adm0_name")["guid"]
        .nunique()
        .reset_index(name="unmatched_districts")
        .sort_values("unmatched_districts", ascending=False)
    )
    print("Unmatched district counts by country (adm0_name):")
    print(counts_by_adm0.to_string(index=False))

# Keep only districts matched in the shapefile
cases = cases[cases["dot_name"].notna()].copy()

# Drop future months
cases = cases[cases["month_start"] <= pd.Timestamp.now().strftime("%Y-%m-%d")]

# Summary by country before finalizing
cases["year"] = pd.to_datetime(cases["month_start"]).dt.year
totals = cases.groupby("adm0_name").agg(
    cases=("cases", "sum"),
    min_year=("year", "min"),
    max_year=("year", "max"),
)
totals["cases"] = totals["cases"].astype(int)
totals = totals.sort_values("cases", ascending=False)
print("\nTotal cases by country:")
print(totals.to_string())

# Final column order
cases = cases[["dot_name", "guid", "month_start", "cases"]]

# Save in Pandas-native HDF5 format
today = pd.Timestamp.now().strftime("%Y%m%d")
output_path = f"data_local/curated/epi_africa_{today}.h5"
cases.to_hdf(output_path, key="epi", mode="w", format="table", complevel=5)

print(f"\nSaved {len(cases)} rows to {output_path}")
print("Done")
