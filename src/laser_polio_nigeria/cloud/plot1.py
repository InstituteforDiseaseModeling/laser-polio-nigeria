import pandas as pd
import matplotlib.pyplot as plt

# Load the CSV
df = pd.read_csv("sim_results_k8s_fast_from_pop.csv")

# Group by node and sum infections to find top 20 nodes
total_infections_by_node = df.groupby("node")["P"].sum()
top_20_nodes = total_infections_by_node.sort_values(ascending=False).head(20).index

# Filter the DataFrame to only those top 20 nodes
top_df = df[df["node"].isin(top_20_nodes)]

# Pivot so each node's infection time series is a column
pivot_df = top_df.pivot(index="date", columns="node", values="P")

# Sort columns (optional, by total infections)
pivot_df = pivot_df[top_20_nodes]

# Plot
plt.figure(figsize=(14, 8))
pivot_df.plot()
plt.title("Infections Over Time - Top 20 Nodes")
plt.xlabel("Date")
plt.ylabel("Number of Infected Individuals (I)")
plt.legend(title="Node", bbox_to_anchor=(1.05, 1), loc='upper left')
plt.tight_layout()
plt.grid(True)
plt.show()
