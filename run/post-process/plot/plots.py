import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os
import argparse

# ==========================================
# CONFIGURATION VARIABLES
# ==========================================

parser = argparse.ArgumentParser(description="General plots comparing Speedup to various attributes")
parser.add_argument('--csv-dir', required=True, help="Directory to read in the CSV files from.")
parser.add_argument('--plot-dir', required=True, help="Directory to save the resulting plots (png files).")
args = parser.parse_args()

FIGURE_DIR = args.plot_dir
SOLVER_CSV = os.path.join(args.csv_dir, 'solver_times.csv')
MPI_CSV    = os.path.join(args.csv_dir, 'mpi_stats.csv')

# Experiment configurations
BASELINE_BACKEND = "mpi"
OTHER_BACKENDS = ["rccl", "st"]
MATRICES = ["audikw_1", "Queen_4147", "Serena"]

# Visual customizations
BACKEND_COLORS = {
    "st": "royalblue",
    "rccl": "crimson"
}

MATRIX_MARKERS = {
    "audikw_1": "o",
    "Queen_4147": "s",
    "Serena": "^"
}

# ==========================================
# Plot function
# ==========================================
def acg_plot(x_data, x_data_name, x_data_label):
    # 4. Merge X and Y data
    plot_data = pd.merge(df_solver, x_data, on=['total_ranks', 'matrix'], how='inner')

    # Filter for the plots
    plot_data = plot_data[plot_data['backend'].isin(OTHER_BACKENDS)]
    plot_data = plot_data[plot_data['matrix'].isin(MATRICES)]

    plt.figure(figsize=(10, 6))

    ax = sns.lineplot(
        data=plot_data,
        x=x_data_name,
        y='Percent Speedup Improvement',
        hue='backend',
        style='matrix',
        palette=BACKEND_COLORS,
        markers=MATRIX_MARKERS,
        dashes=False,           
        errorbar=('ci', 95)     
    )

    plt.xscale('log', base=2)
    plt.grid()
    plt.axhline(0, color='black', linestyle='--', linewidth=1, alpha=0.5) 
    plt.xlabel(f'{x_data_label} [Log Scale]')
    plt.ylabel(f'Point Change in Speedup vs {BASELINE_BACKEND}')
    plt.title(f'Change in Parallel Efficiency vs {x_data_label} relative to {BASELINE_BACKEND}')

    plt.legend(title='Legend', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()

    output_file=(f'speedup-{x_data_name}.png').replace(" ", "_")
    plt.savefig(os.path.join(FIGURE_DIR, output_file), dpi=300, bbox_inches='tight')
    print(f"Plot successfully generated and saved to {os.path.join(FIGURE_DIR, output_file)}")

# ==========================================
# DATA PROCESSING
# ==========================================

# 1. Read CSVs
df_solver = pd.read_csv(SOLVER_CSV)
df_mpi = pd.read_csv(MPI_CSV)

# Calculate total ranks
df_solver['total_ranks'] = df_solver['nodes'] * df_solver['ppn']
df_mpi['total_ranks'] = df_mpi['nodes'] * df_mpi['ppn']

# 2. Process MPI Stats for X-axis (Average Message Size)
df_mpi = df_mpi[df_mpi['matrix'].isin(MATRICES)]
df_mpi['rank_avg_msg_size'] = df_mpi['bytes sent per iteration'] / df_mpi['messages sent per iteration'].replace(0, np.nan)

# For Plot 1
x_data_avg_msg_size = df_mpi.groupby(['total_ranks', 'matrix'])['rank_avg_msg_size'].mean().reset_index()
x_data_avg_msg_size.rename(columns={'rank_avg_msg_size': 'avg_msg_size'}, inplace=True)

# For Plot 2
# Filter out 1 rank runs, as those don't send anything
x_data_tbs = df_mpi[df_mpi['total_ranks'] > 1]
x_data_tbs = x_data_tbs.groupby(['total_ranks', 'matrix', 'rank'])['bytes sent per iteration'].mean().reset_index()
x_data_tbs = x_data_tbs.groupby(['total_ranks', 'matrix'])['bytes sent per iteration'].mean().reset_index()

# For Plot 3
# Filter out 1 rank runs, as those don't send anything
x_data_msg_count = df_mpi[df_mpi['total_ranks'] > 1]
x_data_msg_count = x_data_msg_count.groupby(['total_ranks', 'matrix', 'rank'])['messages sent per iteration'].mean().reset_index()
x_data_msg_count = x_data_msg_count.groupby(['total_ranks', 'matrix'])['messages sent per iteration'].mean().reset_index()

# 3. Process Solver Times for Y-axis (User's Parallel Efficiency/Speedup)
# Create the pivot_df as requested to find the 'min' runtime
pivot_df = df_solver.groupby(['system', 'matrix', 'total_ranks', 'backend'])['solver_time'].agg(['min', 'mean']).reset_index()
pivot_df.set_index(['system', 'matrix', 'total_ranks', 'backend'], inplace=True)

# Isolate baseline data to find the minimum ranks per problem
df_base = df_solver[df_solver['backend'] == BASELINE_BACKEND]

def speedup_func(row):
    system = row['system']
    matrix = row['matrix']
    
    # Dynamically find the smallest number of ranks for this system/matrix from the baseline
    mask = (df_base['system'] == system) & (df_base['matrix'] == matrix)
    if not mask.any():
        return np.nan
        
    speedup_base = df_base[mask]['total_ranks'].min()

    try:
        base_rt = pivot_df.loc[(system, matrix, speedup_base, BASELINE_BACKEND), 'min']
        return (speedup_base * base_rt) / row['solver_time']
    except KeyError:
        return np.nan

def relative_speedup_func(row):
    base_speedup = speedup_df.loc[(row['system'], row['matrix'], row['nodes'], row['total_ranks'], BASELINE_BACKEND), 'mean']
    return 100 * (row['speedup'] - base_speedup) / base_speedup

# Apply your speedup function
df_solver['speedup'] = df_solver.apply(speedup_func, axis=1)

speedup_df = pd.pivot_table(df_solver,
                     index = ["system", "matrix", 'nodes', 'total_ranks', 'backend'],
                     values = ["speedup"],
                     aggfunc = ["min", "mean", "std", "max"])
speedup_df.columns = speedup_df.columns.droplevel(1)
df_solver['Percent Speedup Improvement'] = df_solver.apply(relative_speedup_func, axis=1)

# Because the baseline (BASELINE_BACKEND) now has a scaling curve rather than a flat 1.0, 
# "point change in speedup" means we must subtract BASELINE_BACKEND's speedup at that specific rank count.
baseline_speedups = df_solver[df_solver['backend'] == BASELINE_BACKEND].groupby(['total_ranks', 'matrix'])['speedup'].mean().reset_index()
baseline_speedups.rename(columns={'speedup': 'base_avg_speedup'}, inplace=True)

df_solver = pd.merge(df_solver, baseline_speedups, on=['total_ranks', 'matrix'], how='inner')
df_solver['speedup_change'] = df_solver['speedup'] - df_solver['base_avg_speedup']

# ==========================================
# PLOTTING
# ==========================================
acg_plot(x_data_avg_msg_size, 'avg_msg_size', "Average Message Size (Bytes)")
acg_plot(x_data_tbs, 'bytes sent per iteration', "Bytes Sent per Iteration (averaged across all ranks) (Bytes)")
acg_plot(x_data_msg_count, 'messages sent per iteration', "Messages Sent Per Iteration (averaged across all ranks)")
