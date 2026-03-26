#!/usr/bin/env python
# coding: utf-8

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sbn
import glob

palette = {
    'Cray MPICH Send': 'tab:green',
    'Stream-Triggered Send': 'tab:blue',
    'audikw_1':'tab:blue',
    'Bump_2911':'tab:green',
    'Cube_Coup_dt0':'tab:orange',
    'Flan_1565':'tab:red',
    'Queen_4147':'tab:purple',
    'Serena':'tab:gray'

}

system_order = ["Frontier", "Tuolumne"]
full_backend_order = ["Cray MPICH Send", "Stream-Triggered Send"]
matrix_order = ['audikw_1', 'Bump_2911', 'Cube_Coup_dt0', 'Flan_1565', 'Queen_4147', 'Serena']

def setup_kargs_and_title(k, breakdown, hue, style):
    k["height"] = 3.5
    k["aspect"] = 1.25
    if hue != "":
        k["hue"] = hue
        k["palette"] = palette
    if style != "":
        k["style"] = style

    if breakdown == "System":
        k["col_order"] = system_order
        k["col"] = "System"
        title = "{col_name}"
    elif breakdown != "":
        title = "{row_name}" + " {col_name} " + breakdown
        k["row"] = "System"
        k["col"] = breakdown
    else:
        title = ""

    if hue == "Backend":
        k["hue_order"] = full_backend_order
    elif hue == "Matrix":
        k["hue_order"] = matrix_order

    return title

def make_runtime_plot(data, x, yscale, breakdown, style="Problem Size (GB)", hue="Backend", extra=""):
    kargs = {}
    title = setup_kargs_and_title(kargs, breakdown, hue, style)
 
    runtime_plot = sbn.relplot(data=data, kind="line", x=x, y="Solve Time", 
                               errorbar=("ci", 95), 
                               markers=True, **kargs)
    runtime_plot.set_titles(title)
    for ax in runtime_plot.axes.ravel():
        ax.grid(True, axis='both', ls=':')
    plt.xscale('log', base=2)
    if yscale == 'log':
        plt.yscale('log', base=10)
    plt.savefig(f"Runtime-{x}-{breakdown}-{yscale}{extra}.png")
    plt.close()

def make_speedup_plot(data, x, yscale, breakdown, style="Matrix", hue="Backend", extra=""):
    kargs = {}
    title = setup_kargs_and_title(kargs, breakdown, hue, style)

    speedup_plot = sbn.relplot(data=data, kind="line", x=x, y="Speedup", 
                               errorbar=("ci", 95), 
                               markers=True, **kargs)
    speedup_plot.set_titles(title)
    for ax in speedup_plot.axes.ravel():
        ax.grid(True, axis='both', ls=':')
        if yscale == 'log':
            ax.axline((0, 0), slope=1, color='k', ls='--')
    plt.xscale('log', base=2)
    if yscale == 'log':
        plt.yscale('log', base=2)
    plt.savefig(f"Speedup-{x}-{breakdown}-{yscale}{extra}.png")
    plt.close()

def make_percent_plot(data, x, breakdown, y="Speedup", style="Backend", invertx=False, extra=""):
    ### Relative improvement in speedup by Problem Size
    mpiadvancedata = data[ data['Backend'].isin(["Stream-Triggered Send"]) ]
    kargs = {}
    title = setup_kargs_and_title(kargs, breakdown, "Matrix", style)
    print(mpiadvancedata)
   
    percent_plot = sbn.relplot(data=mpiadvancedata, kind="line", x=x, 
                               y=f"Percent {y} Improvement",
                               errorbar=("ci", 95),
                               markers=True, **kargs)
    percent_plot.set_titles(title)
    plt.xscale('log', base=2)
    for ax in percent_plot.axes.ravel():
        ax.grid(True, axis='both', ls=':')
        if invertx:
            ax.invert_xaxis()
    plt.savefig(f"Percent-{y}-{x}-{breakdown}-linear{extra}.png")
    plt.close()

# Read the raw data into a Pandas Data Frame
all_files = glob.glob("results3.csv")
df = pd.concat((pd.read_csv(f) for f in all_files), ignore_index=True)

# Fix the labels of the columns to be more readable
df = df.rename(columns={'nodes':'Nodes', 'ntasks':'GPUs per Node', 
          'solver_time':'Solve Time', 'system':'System', 'backend':'Backend', 'date': "Date", 'matrix':"Matrix"})

# Fix the names of the backends to be more readable
df['Backend'] = df['Backend'].replace({"st":"Stream-Triggered Send",
                                       "mpi":"Cray MPICH Send"})
# Fix the names of the backends to be more readable
df['System'] = df['System'].replace({"tioga":"Tioga",
                                     "tuolumne":"Tuolumne",
                                     "TUOLUMNE":"Tuolumne",
                                     "frontier":"Frontier"})


# Compute derived values to use to generate data to plot from measured terms
## The total number of MPI ranks used in a sample
df['Ranks'] = df['Nodes'] * df['GPUs per Node']
df = df.sort_values(['Ranks','Nodes'])

## Compute speedup and parallel efficiency
### Aggregate the minimum, mean, and variance of the solver time using 
### a pivot table to calculate a base value to use for calculating speedup 
### calculations using a pivot table
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.max_colwidth', None)
pivot_df = pd.pivot_table(df, 
                     index = ["System", "Matrix", "Ranks", "Backend"],
                     values = ["Solve Time"],
                     aggfunc = ["min", "mean", "std"])
pivot_df.columns = pivot_df.columns.droplevel(1)
#print(pivot_df)

### Now compute the speedup, parallel efficiency with the baseline as the best runtime 
### from an execution on the smallest number of ranks in the data set for a given problem 
### from the original Cray backend
speedup_base = 1;
def speedup_func(row):
    base_rt = pivot_df.loc[row['System'], row['Matrix'], speedup_base, "Cray MPICH Send"]["min"]
    return speedup_base * base_rt / row['Solve Time']

df['Speedup'] = df.apply(speedup_func, axis=1)

# Now summarize/compute averages by node/rank combination
speedup_df = pd.pivot_table(df,
                     index = ["System", "Matrix", 'Nodes', 'Ranks', 'Backend'],
                     values = ["Speedup"],
                     aggfunc = ["min", "mean", "std", "max"])
speedup_df.columns = speedup_df.columns.droplevel(1)

# # Calculate speedup and efficiency on a node/rank basis compared to the
# # identical node/rank configuration.
def relative_speedup_func(row):
    base_speedup = speedup_df.loc[row['System'], row['Matrix'], row['Nodes'], row['Ranks'], "Cray MPICH Send"]["mean"]
    return 100 * (row['Speedup'] - base_speedup) / base_speedup

df['Percent Speedup Improvement'] = df.apply(relative_speedup_func, axis=1)

speedupdata=df[  df['Backend'].isin([
    "Stream-Triggered Send", 
    "Cray MPICH Send"])
              ]
tuodata=speedupdata[ speedupdata['System'].isin(["Tuolumne"]) ]

make_speedup_plot(data=tuodata, x="Ranks", yscale="log", breakdown="", extra="-Tuolumne")
make_speedup_plot(data=tuodata, x="Ranks", yscale="linear", breakdown="", extra="-Tuolumne")
make_percent_plot(data=tuodata, x='Ranks', breakdown="", extra="-Tuolumne")

## On tuolumne (but not Frontier), the speedup for Cray MPICH is highly dependent on PPN 
## Break these down separately by system since they have different PPNs they can support
make_speedup_plot(data=tuodata, x="Ranks", yscale="log", breakdown="GPUs per Node", extra="-Tuolumne")
make_speedup_plot(data=tuodata, x="Ranks", yscale="linear", breakdown="GPUs per Node", extra="-Tuolumne")
make_percent_plot(data=tuodata, x='Ranks', breakdown="GPUs per Node", extra="-Tuolumne")
