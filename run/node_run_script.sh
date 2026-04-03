#!/bin/bash
#flux: --gpus-per-slot=1
#flux: --exclusive
#flux: --env=FLUX_TO_BASH={{nnodes}}

# Modules to run
module load rocm/6.4.3 craype-accel-amd-gfx942 
# Environment variables to set
## Turn on GPU-AWARE Cray MPICH
export MPICH_GPU_SUPPORT_ENABLED=1
export OMP_NUM_THREADS=7
## Get that special RCCL
RCCL_PLUGIN=/g/g16/derek/apps/nccl-plugin
#RCCL_PLUGIN=/g/g16/derek/apps/rccl-plugin
export LD_LIBRARY_PATH="${RCCL_PLUGIN}/lib:${LD_LIBRARY_PATH}"

# Variable Setup (including variables pulled from top level script/flux) 
NODES=$FLUX_TO_BASH
START_PPN_POWER=0
END_PPN_POWER=2
ACG_EXE=/g/g16/derek/git/aCG/build/acg-hip
MXT_EXE=/g/g16/derek/git/aCG/build2/mtxpartition

#MATRICES=("poisson1d_1073741824")
MATRICES=("audikw_1" "Bump_2911" "Cube_Coup_dt0" "Flan_1565" "Queen_4147" "Serena" "nd24k" "ldoor")
#MATRICES=("audikw_1" "Serena")
#MATRICES=("Pflow73m")
MODES=("mpi" "rccl" "st")
#MODES=("mpi" "st")

#ulimit -c unlimited
ulimit -c 0
#ROCPROF_EXE="rocprofv3 --output-directory /usr/workspace/derek/out --sys-trace --output-format pftrace --"

# Scale through PPN
for (( exp=START_PPN_POWER; exp<=END_PPN_POWER; exp++ )); do
    PPN=$((2 ** $exp))
    PARTITIONS=$(($NODES*$PPN))
    for MATRIX in "${MATRICES[@]}"; do
        # Which files to use for the given matrix
        MATRIX_FILE="/usr/workspace/derek/aCG/input/$MATRIX.mtx"
        if [ "$MATRIX" == "poisson1d_1073741824" ]; then
            MATRIX_FILE="--binary /usr/workspace/derek/aCG/input/$MATRIX.mtxbin32"
        fi
        PARTITION_FILE="/usr/workspace/derek/aCG/partitions/${MATRIX}_${PARTITIONS}_parts.mtx"
        # Make partition file if necessary
        if [[ ! -f "$PARTITION_FILE" ]]; then
            echo "Partition file not found -- making"
            ${MXT_EXE} --verbose --verbose --verbose --parts=$PARTITIONS $MATRIX_FILE \
            > $PARTITION_FILE
        fi

        JOB_NAME="${MATRIX}_${NODES}_${PPN}"
        for MODE in "${MODES[@]}"; do
            # Flags for specific modes:
            if [ "$MODE" == "rccl" ]; then
                export NCCL_NET_GDR_LEVEL=PHB
                export NCCL_CROSS_NIC=1
                export HSA_FORCE_FINE_GRAIN_PCIE=1
                export FI_MR_CACHE_MONITOR=userfaultfd
                export FI_CXI_DISABLE_HOST_REGISTER=1
                export FI_CXI_DEFAULT_CQ_SIZE=131072
                export FI_CXI_RDZV_PROTO=alt_read
                export FI_CXI_RX_MATCH_MODE=hybrid
                export FI_CXI_RDZV_EAGER_SIZE=0
                export FI_CXI_DEFAULT_TX_SIZE=2048
                #export NCCL_DEBUG=INFO
            fi

            flux run --setopt=mpibind=verbose:1 -x --nodes=$NODES --tasks-per-node=$PPN \
            --job-name="$JOB_NAME" --output="${ACG_OUT}/${JOB_NAME}.out" -o output.mode=append \
            ${ROCPROF_EXE} ${ACG_EXE} ${MATRIX_FILE} \
            --partition=${PARTITION_FILE} \
            --seed 101 --residual-atol 0 --residual-rtol 1e-6 --max-iterations 100000 \
            --solver acg --comm $MODE --manufactured-solution --verbose -q

            # Cleanup for specific modes
            if [ "$MODE" == "rccl" ]; then
                unset NCCL_NET_GDR_LEVEL
                unset NCCL_CROSS_NIC
                unset HSA_FORCE_FINE_GRAIN_PCIE
                unset FI_MR_CACHE_MONITOR
                unset FI_CXI_DISABLE_HOST_REGISTER
                unset FI_CXI_DEFAULT_CQ_SIZE
                unset FI_CXI_RDZV_PROTO
                unset FI_CXI_RX_MATCH_MODE
                unset FI_CXI_RDZV_EAGER_SIZE
                unset FI_CXI_DEFAULT_TX_SIZE
                #unset NCCL_DEBUG
            fi
        done
    done
done
