#!/bin/bash

BASE_DIR="output_onenode_r0sweep"
SCRIPT="sweep_and_score_ref.py"
DIR_PREFIX="r0"
CSV_NAME="synth_data.csv"

for SUBDIR in "$BASE_DIR"/${DIR_PREFIX}_*; do
    if [ -d "$SUBDIR" ]; then
        # Extract float after r0_
        REF_PARAM=$(basename "$SUBDIR" | sed 's/^r0_//')

        # Path to synth_data.csv
        REF_CSV="$SUBDIR/$CSV_NAME"

        if [ ! -f "$REF_CSV" ]; then
            echo "[WARN] Missing $CSV_NAME in $SUBDIR, skipping..."
            continue
        fi

        echo "[INFO] Running scoring for R0 = $REF_PARAM"
        
        python "$SCRIPT" \
            --ref-synth-csv "$REF_CSV" \
            --base-dir "$BASE_DIR" \
            --dir-prefix "${DIR_PREFIX}_" \
            --file-glob "*.csv" \
            --ref-param "$REF_PARAM" \
            --outdir "$SUBDIR/score_vs_ref"

        echo
    fi
done
