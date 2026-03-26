#!/usr/bin/env python3
import sys

# Usage: grep <flags> <pattern> <file(s)> | python3 parse_outputs.py > results.csv

#mode_dict = {0: "mpi", 1: "rccl"}
mode_dict = {0: "mpi", 1: "st"}
mode = 0

# Print top row.
print("nodes,ntasks,matrix,backend,solver_time,system,date")

for line in sys.stdin:
    # Remove trailing newline
    line = line.rstrip("\n")
    
    # Break off time
    file, _, time = line.split(":")
    # Remove "Seconds"
    time = time.strip().split(" ")[0]

    # Break off matrix name
    data = file.split("/")
    config = data[-2]
    matrix = data[-1]
    # Remove file extension
    matrix = matrix.split(".")[0]
    # Split up matrix and ppn
    matrix, ppn = matrix.rsplit("_", 1)
    # Peel off node (not saving this one)
    matrix, _ = matrix.rsplit("_", 1)

    # Split off system
    system, config = config.split("-",1)
    # Split off nodes
    nodes, date = config.split("-",1)
    # Peel off run number
    date, _ = date.rsplit("-", 1)

    print(nodes, ppn, matrix, mode_dict[mode], time, system, date, sep=",")
    # Two modes per file (so for the next line, switch to other mode)
    mode ^= 1

