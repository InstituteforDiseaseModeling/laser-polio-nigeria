# laser-polio-nigeria

This repository contains tools, curated data scripts, and utilities to support regional and national-scale polio modeling with the LASER platform. It serves as a research support layer — but not the model implementation itself.

### What's in this repo?

- 🧪 Tools for:
  - Curating population, birth rate, age structure, and shapefile data
  - Compiling polio-relevant individual risk and vaccination history datasets
- 📊 Scripts for:
  - Plotting simulation and case data
  - Exploring and validating sweep results
- 🗂️ Configs and utilities for:
  - Launching large-scale response SIA simulations
  - Analyzing spatial and temporal outputs

### What’s **not** in this repo?

- ❌ LASER model code → see [`laser-core`](https://github.com/your-org/laser-core)
- ❌ Calibration logic → see [`laser-polio-calibration`](https://github.com/your-org/laser-polio-calibration)
- ❌ Large input datasets → now hosted as a versioned external [data product](https://your-artifactory-url)

### Recommended Setup

This repo is designed to work in tandem with `laser-core`, `laser-polio-calibration`, and the `laser-polio-nigeria-data` product.

