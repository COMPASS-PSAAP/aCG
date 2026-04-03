import argparse
import csv
import os
import re
from collections import defaultdict

def main():
    parser = argparse.ArgumentParser(description="Parse solver times from grep output.")
    parser.add_argument('--input', required=True, help='Input grep output file')
    parser.add_argument('--output', required=True, help='Output CSV file')
    args = parser.parse_args()

    backends = ["mpi", "rccl", "st"] 

    # Captures: 1=dir, 2=file, 3=solver_time
    line_pattern = re.compile(
        r'^(.+)/([^:]+):\s*(?:total\s+)?solver time:\s+([\d.]+)\s+seconds'
    )

    # Dictionary to track the number of matches per file
    file_match_counts = defaultdict(int)

    with open(args.output, 'w', newline='') as fout:
        writer = csv.writer(fout)
        writer.writerow(['system', 'nodes', 'ppn', 'matrix', 'backend', 'solver_time'])

        with open(args.input, 'r') as fin:
            for line in fin:
                match = line_pattern.search(line)
                if not match: continue
                
                full_path, file_name, solver_time = match.groups()
                dir_name = os.path.basename(os.path.normpath(full_path))
                system = dir_name.split('-')[0]

                base = file_name.replace('.out', '')
                try:
                    matrix, nodes, ppn = base.rsplit('_', 2)
                except ValueError:
                    continue

                # Determine the nth match for this specific file
                full_file_path = f"{dir_name}/{file_name}"
                n = file_match_counts[full_file_path]
                
                # Safely get the backend name (with a fallback if matches exceed array length)
                if n < len(backends):
                    backend = backends[n]
                else:
                    backend = f"unnamed_backend_{n}"
                    
                # Increment the match count for the next time we see this file
                file_match_counts[full_file_path] += 1

                writer.writerow([system, nodes, ppn, matrix, backend, solver_time])

if __name__ == '__main__':
    main()