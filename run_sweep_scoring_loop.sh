#!/bin/bash

# Usage: ./run_sweep_scoring_loop.sh output_onenode_r0eq10_spdeq150

BASE_DIR="$1"
if [ -z "$BASE_DIR" ]; then
    echo "Usage: $0 <base_dir>"
    exit 1
fi

SCRIPT="sweep_and_score_ref.py"

# Optional: name of the CSV inside each subdir
CSV_NAME="synth_data.csv"

# Output directory inside each sweep dir
OUTDIR_NAME="score_vs_ref"

# Loop over all matching subfolders
for REF_DIR in "$BASE_DIR"/seasonal_amplitude_*; do
    if [ -d "$REF_DIR" ]; then
        # Extract float value from folder name
        REF_PARAM=$(basename "$REF_DIR" | sed 's/[^0-9.]//g')
        REF_CSV="$REF_DIR/$CSV_NAME"

        if [ ! -f "$REF_CSV" ]; then
            echo "[WARN] Missing $CSV_NAME in $REF_DIR"
            continue
        fi

        echo "[INFO] Scoring with reference: $REF_CSV (param = $REF_PARAM)"

        python "$SCRIPT" \
            --ref-synth-csv "$REF_CSV" \
            --base-dir "$BASE_DIR" \
            --dir-prefix seasonal_amplitude_ \
            --file-glob "*.csv" \
            --ref-param "$REF_PARAM" \
            --outdir "$REF_DIR/$OUTDIR_NAME"

        echo "[INFO] Done with $REF_PARAM"
        echo
    fi
done
