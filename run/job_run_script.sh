#!/bin/bash

usage() {
    echo "Usage: $0 [-Q queue] [-E power] [-S power] [-I time]"
    echo " -Q [queue] The flux queue to run the jobs in (default pdebug)"
    echo " -E [power] The power of 2 number of nodes to stop at (inclusive, default 2 (4 nodes))"
    echo " -S [power] The power of 2 number of nodes to start at (inclusive, default 0 (1 node))"
    echo " -I [time] The time for the TOTAL job length, in flux notation (Default \"40m\")"
    echo " -R [number] How many times to repeat the sweep (in x,y,z,x,y,z order, not x,x,y,y,z,z) (default 1)"
}

while getopts ":Q:E:S:I:R:" opt; do
    case $opt in
        Q)
            QUEUE="$OPTARG"
            ;;
        E)
            END_EXP="$OPTARG"
            ;;
        S)
            START_EXP="$OPTARG"
            ;;
        I)
            TIME="$OPTARG"
            ;;
        R)
            REPEATS="$OPTARG"
            ;;
        *)
            usage
            exit
            ;;
    esac
done

SYSTEM=TUOLUMNE

# Determine Queue
if [ -z $QUEUE ]; then
    QUEUE=pdebug
fi

# Determine how many times to repeat
if [ -z $REPEATS ]; then
    REPEATS=1
fi

if [ $REPEATS -lt 1 ]; then
    echo "Invalid number of times to run the tests, stopping."
    exit 1
fi

# Determine Node Limits
if [ -z $START_EXP ]; then
    START_EXP=0
fi

if [ -z $END_EXP ]; then
    END_EXP=2
fi

if [ $END_EXP -lt $START_EXP ]; then
    echo "The number nodes specified would result in no runs, stopping."
    exit 1
fi

# Determine total job time limit
if [ -z $TIME ]; then
    TIME=40m
fi

echo "Job node range (powers of 2): $START_EXP:$END_EXP ( for $TIME, on $QUEUE, repeated $REPEATS time(s))"

# Setup Output Filename
SYSTEM=TUOLUMNE
COLLECTION_DIR=outputs

for (( i=0; i<$REPEATS; i++ )); do
    prev_job_id=""
    for (( exp=START_EXP; exp<=END_EXP; exp++ )); do
        NODES=$((2 ** $exp))
        SLOTS=$((4 * $NODES))
        if [ -n "$prev_job_id" ]; then
            dependency_option="--dependency=afterany:$prev_job_id"
        else
            dependency_option=""
        fi

        # Create files for specific run
        FILENAME_BASE="./$COLLECTION_DIR/$SYSTEM-$NODES-$(date +%m-%d)"
        COUNT=1
        TARGET="${FILENAME_BASE}-${COUNT}"

        while [[ -e $TARGET ]]; do
            ((COUNT++))
            TARGET="${FILENAME_BASE}-${COUNT}"
        done

        mkdir "$TARGET"
        echo $TARGET

        # Get allocation for an entire node (launching a script to sweep PPN)
        set -x
        prev_job_id=$(flux batch --time-limit=$TIME --queue=$QUEUE         \
                                    --output="${SYSTEM}-${NODES}-${i}.out" \
                                    --nodes=$NODES --nslots=$SLOTS         \
                                    --job-name="aCG-${NODES}"              \
                                    --env=ACG_OUT=$TARGET                  \
                                    $dependency_option                     \
                                    ./node_run_script.sh)
        set +x
    done
done