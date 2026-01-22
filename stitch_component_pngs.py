#!/usr/bin/env python3
import sys
import os
import glob
import re
from PIL import Image
import math

def extract_param_value(path):
    """Extract float from folder names like 'seasonal_peak_doy_152.07' or 'r0_12.41'"""
    match = re.search(r'(seasonal_amplitude|seasonal_peak_doy|r0)_(\d+\.?\d*)', path)
    return float(match.group(2)) if match else None

def main():
    if len(sys.argv) < 2:
        print("Usage: python stitch_component_pngs.py <base_dir>")
        sys.exit(1)

    base_dir = sys.argv[1]

    # Handle both types of naming conventions
    subdir_patterns = ["seasonal_amplitude_*", "seasonal_peak_doy_*", "r0_*"]
    png_paths = []

    for pattern in subdir_patterns:
        pattern_path = os.path.join(base_dir, f"{pattern}/score_vs_ref/component_nll_vs_param.png")
        png_paths.extend(glob.glob(pattern_path))

    # Build a list of (param_value, path) pairs
    scored_paths = []
    for path in png_paths:
        val = extract_param_value(path)
        if val is not None:
            scored_paths.append((val, path))
        else:
            print(f"[WARN] Skipping unrecognized path: {path}")

    if not scored_paths:
        print("[ERROR] No matching PNGs found.")
        sys.exit(1)

    # Sort by param value
    scored_paths.sort(key=lambda x: x[0])

    # Load images
    images = [Image.open(p) for _, p in scored_paths]
    widths, heights = zip(*(img.size for img in images))

    # Layout: N columns, compute rows
    ncols = 5
    nimgs = len(images)
    nrows = math.ceil(nimgs / ncols)

    # Assume all images same size
    img_w = max(widths)
    img_h = max(heights)

    # Create blank canvas
    stitched = Image.new("RGB", (ncols * img_w, nrows * img_h), color="white")

    # Paste images in grid
    for idx, img in enumerate(images):
        row = idx // ncols
        col = idx % ncols
        stitched.paste(img, (col * img_w, row * img_h))

    # Output
    outpath = os.path.join(base_dir, "stitched_component_nll_grid.png")
    stitched.save(outpath)
    print(f"[INFO] Saved stitched image to: {outpath}")

if __name__ == "__main__":
    main()
