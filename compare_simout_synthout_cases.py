#!/usr/bin/env python3
import sys
import pandas as pd
import matplotlib.pyplot as plt

def main():
    if len(sys.argv) < 3:
        print("Usage: python plot_compare.py <simulation_results.csv> <synth_data.csv>")
        sys.exit(1)

    sim_file = sys.argv[1]
    synth_file = sys.argv[2]

    # Load simulation output
    df_sim = pd.read_csv(sim_file)
    df_sim['date'] = pd.to_datetime(df_sim['date'])

    if 'new_potentially_paralyzed' not in df_sim.columns:
        raise ValueError("Missing 'new_potentially_paralyzed' in simulation file.")

    # Monthly aggregation from sim
    sim_monthly = (
        df_sim.groupby(df_sim['date'].dt.to_period('M'))['new_potentially_paralyzed']
        .sum()
        .to_timestamp()
        .rename("sim_new_potentially_paralyzed")
    )

    # Load synth_data
    df_synth = pd.read_csv(synth_file)
    df_synth['month_start'] = pd.to_datetime(df_synth['month_start'])

    # Aggregate synth by month (across regions)
    synth_agg = df_synth.groupby('month_start')[['new_potentially_paralyzed', 'cases']].sum().reset_index()
    synth_agg.set_index('month_start', inplace=True)

    # Align indexes for plotting
    combined = pd.DataFrame({
        'sim_new_potentially_paralyzed': sim_monthly,
        'synth_new_potentially_paralyzed': synth_agg['new_potentially_paralyzed'],
        'synth_cases': synth_agg['cases']
    }).dropna(how='all')  # Drop rows where all series are missing

    # Print table
    print("\nCombined monthly time series:")
    print(combined.to_string(index=True))

    # Plot
    plt.figure(figsize=(11, 6))
    plt.plot(combined.index, combined['sim_new_potentially_paralyzed'], marker='o', label='Simulation: New Potentially Paralyzed')
    plt.plot(combined.index, combined['synth_new_potentially_paralyzed'], marker='s', label='Reference: New Potentially Paralyzed')
    #plt.plot(combined.index, combined['synth_cases'], marker='^', label='Reference: Cases')

    plt.title("Monthly Outputs: Simulation vs Reference", pad=20)
    plt.xlabel("Month")
    plt.ylabel("Count")
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
