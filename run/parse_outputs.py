#!/usr/bin/env python3
import sys

# Usage: grep <flags> <pattern> <file(s)> | python3 parse_outputs.py > results.csv

mode_dict = {0: "mpi", 1: "rccl"}
mode = 0

for line in sys.stdin:
    # Remove trailing newline
    line = line.rstrip("\n")
    
    # Break off time
    file, _, time = line.split(":")
    # Remove "Seconds"
    time = time.strip().split(" ")[0]

    # Break off matrix name
    _, config, matrix, = file.split("/")
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

    print(system, nodes, (int(ppn)*int(nodes)), date, matrix, ppn, time, mode_dict[mode], sep=",")
    # Two modes per file (so for the next line, switch to other mode)
    mode ^= 1

