import sys
import pandas as pd
import matplotlib.pyplot as plt

# Path to your simulation output CSV
#csv_path = "simulation_results.csv"
csv_path = sys.argv[1]

# Load the data
df = pd.read_csv(csv_path)

# Ensure 'date' is a datetime object
df['date'] = pd.to_datetime(df['date'])

# Check required column
if 'new_potentially_paralyzed' not in df.columns:
    raise ValueError("Missing 'new_potentially_paralyzed' column in input CSV.")

# Group by month and sum across all nodes
monthly_paralysis = (
    df.groupby(df['date'].dt.to_period('M'))['new_potentially_paralyzed']
      .sum()
      .to_timestamp()
)

# Plot
plt.figure(figsize=(10, 5))
plt.plot(monthly_paralysis.index, monthly_paralysis.values, marker='o', linestyle='-')
plt.title("Monthly Total New Potentially Paralyzed Cases")
plt.xlabel("Month")
plt.ylabel("Cases")
plt.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()
plt.show()
