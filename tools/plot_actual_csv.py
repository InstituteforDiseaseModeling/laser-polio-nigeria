import sys
import pandas as pd
import matplotlib.pyplot as plt

# Load your CSV
df = pd.read_csv(sys.argv[1], parse_dates=["month_start"])

# Group by month_start and sum across all locations
monthly = df.groupby("month_start")["new_potentially_paralyzed"].sum().reset_index()

# Plot
plt.figure(figsize=(10, 6))
plt.plot(monthly["month_start"], monthly["new_potentially_paralyzed"], marker="o")
plt.title("New Potentially Paralyzed Cases by Month (All Locations)")
plt.xlabel("Month")
plt.ylabel("New Potentially Paralyzed")
plt.grid(True)
plt.tight_layout()
plt.show()
