#!/usr/bin/env python3
import sys
import pandas as pd
import matplotlib.pyplot as plt

def main():
    if len(sys.argv) < 2:
        print("Usage: python plot_synth.py <synth_data.csv>")
        sys.exit(1)

    infile = sys.argv[1]

    # Load CSV
    df = pd.read_csv(infile)

    # Ensure month_start is datetime
    df['month_start'] = pd.to_datetime(df['month_start'])

    # Aggregate across all dot_names (sum over regions)
    agg = df.groupby('month_start')[['new_potentially_paralyzed', 'cases']].sum().reset_index()

    # Print data to console
    print("\nAggregated outputs by month:")
    print(agg.to_string(index=False))

    # Plot both series
    plt.figure(figsize=(10, 6))
    plt.plot(agg['month_start'], agg['new_potentially_paralyzed'], marker='o', label='New Potentially Paralyzed')
    plt.plot(agg['month_start'], agg['cases'], marker='s', label='Cases')

    plt.title("Key Outputs by Month")
    plt.xlabel("Month")
    plt.ylabel("Count")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()