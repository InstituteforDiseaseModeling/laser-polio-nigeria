# Repository Organization Analysis: laser-polio-nigeria

**Analysis Date:** February 3, 2026
**Status:** Transitional - migrating from monolith to modular architecture

## Executive Summary

This repository is in a **transitional state**. Evidence shows you've been splitting a monolith into separate packages (`laser-core`, `laser-polio`, `laser-polio-calibration`), and this Nigeria-specific layer reflects that ongoing migration. The core functionality works, but organizational boundaries are unclear.

**Overall Assessment:**
- **Code Organization Score:** 5/10
- **Repository Maturity:** Transitional
- **Main Issue:** Unclear boundaries between production, development, and exploratory code

---

## Current Directory Structure

```
laser-polio-nigeria/
├── src/laser_polio_nigeria/        # 180 KB, 7 Python files - thin wrappers
│   ├── run_sim.py                  # Main: build_nigeria_inputs()
│   ├── calibration/                # Wrappers for calibration integration
│   ├── comps/                      # Legacy COMPS/idmtools integration
│   └── utilities                   # Version checking, file retrieval
│
├── config/                         # 232 KB - all simulation configs
│   ├── model_configs/              # 14 production model configurations
│   └── calib_configs/              # 50+ calibration parameter configs
│
├── data_curation_scripts/          # 912 KB, 14 files - ETL pipelines
│   ├── age/                        # Age structure curation
│   ├── cbr/                        # Crude birth rate data
│   ├── epi/                        # Epidemiological data
│   ├── individual_risk/            # Individual risk factors
│   ├── pop/                        # Population data
│   ├── ri/                         # Routine immunization
│   ├── sia/                        # Supplementary immunization activities
│   ├── shp/                        # Shapefiles and distance matrices
│   ├── random_effects/             # Random effect parameters
│   ├── init_immunity/              # Initial immunity states
│   └── compile_curated_data.py    # Master compiler
│
├── scripts/                        # 432 KB, 48 Python files
│   ├── response_sia_sweep/         # Full parameter sweep pipeline (17 files)
│   │   ├── core/                   # Main sweep logic
│   │   ├── configs/                # 9 sweep-specific configs
│   │   ├── docker/                 # Sweep-specific Docker setup
│   │   ├── jobs/                   # Kubernetes job templates
│   │   └── utils/                  # Sweep utilities
│   └── sandbox/                    # 33 exploratory/debugging scripts (UNORGANIZED)
│
├── examples/                       # 52 KB, 11 demo scripts
│   ├── demo_africa.py
│   ├── demo_nigeria.py
│   ├── demo_zamfara.py
│   └── ... (8 more demos)
│
├── tools/                          # 104 KB - standalone utilities
│   ├── plot_sweep_cases.py
│   ├── plot_cases_by_month.py
│   ├── inspect_h5.py
│   └── ... (plotting and analysis tools)
│
├── docker/                         # 24 KB - Docker infrastructure
│   ├── Dockerfile                  # Which is canonical?
│   ├── Dockerfile_base
│   └── utilities
│
├── docs/                           # 948 KB - Sphinx documentation
├── nigeria_polio_data/             # 228 MB - curated datasets
├── results/                        # 12 MB - simulation outputs
└── tests_scientific/               # Scientific validation tests
```

---

## Major Problems Identified

### 1. Response SIA Sweep is a Mini-Application

**Location:** `scripts/response_sia_sweep/`

**Problem:**
- 17 Python files across 4 subdirectories
- 50+ configuration files
- Own Docker image and Kubernetes job templates
- Multi-config submit/download pipeline
- Complete orchestration system

**Impact:**
- Difficult to version independently
- Unclear if it's part of the package or a separate tool
- Over-complicates this repository

**Recommendation:**
- **Option A:** Extract to its own package (`laser-polio-response-sweep`)
- **Option B:** Move to `tools/` and clearly document as standalone tool
- **Option C:** Keep but add clear README and treat as a sub-project

---

### 2. Sandbox is an Unorganized Dumping Ground

**Location:** `scripts/sandbox/`

**Problem:**
- 33 files with no organization or documentation
- Mix of purposes:
  - Debugging: `debug_dirichlet.py`, `debug_negative_network.py`
  - Validation: `check_sias.py`, `check_targets.py`
  - Analysis: `plot_actual_cases.py`, `calib_sketch.py`
  - Exploration: Various ad-hoc scripts
- No indication of what's current vs obsolete
- No clear lifecycle management

**Impact:**
- Future developers won't know what's safe to delete
- Difficult to find relevant scripts
- Maintenance burden unclear

**Recommendation:**
Reorganize into clear categories:
```
scripts/
├── validation/          # Production validation tools
├── debugging/           # Active debugging utilities
├── analysis/            # Data analysis scripts
└── legacy/              # Deprecated/exploratory code
```

---

### 3. Three Different Dockerfiles

**Locations:**
- `/Dockerfile` (root)
- `/docker/Dockerfile`
- `/docker/Dockerfile_base`
- `/scripts/response_sia_sweep/docker/Dockerfile`

**Problem:**
- No documentation on which is canonical
- Git history shows recent updates to both root and docker/ versions
- Unclear when to use each
- Duplication of build logic

**Recommendation:**
- **Pick one canonical location** (prefer `/docker/Dockerfile`)
- Use build arguments for variants instead of separate files
- Delete or clearly document deprecated ones
- Add a `docker/README.md` explaining the build process

---

### 4. Duplicate Code: curate_epi.py

**Locations:**
- `/data_curation_scripts/epi/curate_epi.py` (27 lines - production)
- `/scripts/sandbox/curate_epi.py` (55 lines - extended/exploratory)

**Problem:**
- Two versions with different implementations
- Unclear which is authoritative
- No clear distinction between production and exploratory versions

**Recommendation:**
- Keep the production version in `/data_curation_scripts/epi/`
- If the sandbox version has useful exploratory logic, extract it to a separate analysis script
- Delete or clearly mark one as deprecated

---

### 5. Config File Sprawl

**Locations:**
- `config/model_configs/` - 14 model configurations
- `config/calib_configs/` - 50+ calibration configs
- `scripts/response_sia_sweep/configs/` - 9 sweep configs
- `scripts/response_sia_sweep/jobs/` - Kubernetes job YAML

**Problem:**
- Configs scattered across 3+ locations
- No clear registry or documentation of what each config does
- Difficult to discover available configurations
- No convention for naming or organization

**Recommendation:**
Create a config registry (e.g., `config/README.md` or `config/MANIFEST.md`):
```markdown
# Configuration Files

## Model Configurations (config/model_configs/)
- `nigeria_full.yaml` - Full national model
- `zamfara_only.yaml` - Zamfara state only
...

## Calibration Configurations (config/calib_configs/)
- Purpose: Optuna sweep parameter definitions
- Count: 50+ files
...

## Response Sweep Configurations
- Location: scripts/response_sia_sweep/configs/
- Purpose: Parameter sweep scenarios
...
```

---

### 6. Fuzzy Boundaries: tools/ vs scripts/ vs examples/

**Problem:**

| Directory | Current Content | Intended Purpose? |
|-----------|----------------|-------------------|
| `tools/` | Plotting utilities, data inspection | Reusable utilities? |
| `scripts/sandbox/` | Also has plotting, plus analysis | Exploratory code? |
| `examples/` | Runnable demos | User-facing demos ✓ |

**Impact:**
- Unclear where to add new analysis code
- Duplication of plotting logic
- Confusion about what's production vs development

**Recommendation:**
Establish clear boundaries:
- **`examples/`** - User-facing demos (keep as-is) ✓
- **`tools/`** - Production-ready, reusable utilities
- **`scripts/validation/`** - Production validation/checking tools
- **`scripts/analysis/`** - Exploratory data analysis
- **`scripts/legacy/`** - Deprecated exploratory code

---

### 7. Unclear Code Ownership After Refactoring

**Evidence from Git History:**
- Commit 606411f: "Moved nigeria calibration configs from laser-polio-calibration"
- Commit 2e8ab32: "Not sure yet if we'll leave some version of these in the calib module yet. WIP."

**Problem:**
- Calibration code delegates to external `laser-polio-calibration` package
- But calibration configs live in this repo at `config/calib_configs/`
- Unclear which package owns the calibration logic vs configuration
- Ambiguous responsibility boundaries

**Recommendation:**
Document the intended architecture:
```
laser-core               → Core simulation engine
laser-polio              → Polio-specific model logic
laser-polio-calibration  → Calibration framework
laser-polio-nigeria      → Nigeria-specific:
                           - Input data curation
                           - Country-specific configs
                           - Analysis tools
                           - Thin integration wrappers
```

---

## src/ Directory Analysis

**Current Structure:**
```
src/laser_polio_nigeria/
├── run_sim.py (324 lines)           # PRIMARY: build_nigeria_inputs()
├── calibration/
│   ├── build_inputs.py (27 lines)   # Wrapper: build_calibrate_nigeria_inputs()
│   └── calibrate.py (28 lines)      # CLI entrypoint, delegates to laser_polio_calibration
├── comps/
│   └── run.py (2024 lines)          # Legacy COMPS/idmtools experiment runner
├── get_lp_module_versions.py       # Dependency introspection
├── find_n_nigeria_nodes.py          # Utility
└── get_files_from_exp.py            # Result retrieval helper
```

**Observations:**
- Very thin abstraction layer (only 7 files)
- Most actual simulation logic delegated to imported `laser_polio` package
- `run_sim.py` is the real workhorse - builds input structures
- `calibration/` is purely a wrapper with minimal logic
- `comps/run.py` is large (2024 lines) but may be legacy

**Assessment:** This is appropriate for a country-specific integration layer. The thin wrapper design is good, but consider:
1. Is `comps/run.py` still actively used? If not, move to legacy
2. Add docstrings explaining the delegation pattern
3. Consider if utilities should be in a separate `utils/` submodule

---

## Data Curation Scripts Analysis

**Current Organization:** ✓ GOOD

```
data_curation_scripts/
├── age/                # Age structure curation
├── cbr/                # Crude birth rate
├── epi/                # Epidemiological data
├── individual_risk/    # Individual risk factors
├── pop/                # Population data
├── ri/                 # Routine immunization
├── sia/                # Supplementary immunization
├── shp/                # Shapefiles & distance matrices
├── random_effects/     # Random effect parameters
├── init_immunity/      # Initial immunity states
└── compile_curated_data.py
```

**Strengths:**
- Well-organized by data modality
- Each subdirectory focused on one data type
- Clear naming convention

**Weakness:**
- No central orchestration or dependency documentation
- `compile_curated_data.py` has hardcoded paths and complex imports
- No manifest documenting execution order or data dependencies

**Recommendation:**
Add `data_curation_scripts/PIPELINE.md`:
```markdown
# Data Curation Pipeline

## Execution Order
1. `pop/` - Must run first (provides base population)
2. `age/`, `cbr/` - Can run in parallel
3. `shp/` - Generates distance matrices
4. `epi/`, `ri/`, `sia/` - Can run in parallel
5. `compile_curated_data.py` - Final compilation

## Dependencies
- pop → age, cbr
- shp → distance matrices
- all → compile_curated_data.py
```

---

## Docker Infrastructure Issues

**Current State:**
- 4 different Dockerfiles in different locations
- Recent git commits show updates to both `/Dockerfile` and `/docker/Dockerfile`
- No clear documentation

**Git History:**
- Commit df32051: "Add automated build script and improve Docker build process"
- Shows active Docker development but unclear consolidation strategy

**Recommendation:**
```
docker/
├── Dockerfile              # Main production image (canonical)
├── Dockerfile.base         # Base image (if needed)
├── README.md              # Build instructions
└── build.sh               # Automated build script (already exists at root)
```

Delete root `/Dockerfile` or add comment redirecting to docker/

---

## Recommended Refactoring Priorities

### Immediate (Quick Wins)

1. **Organize sandbox/ folder**
   ```bash
   mkdir -p scripts/{validation,debugging,analysis,legacy}
   # Move files to appropriate categories
   ```

2. **Pick canonical Dockerfile**
   - Choose `/docker/Dockerfile` as canonical
   - Delete or add deprecation notice to root `/Dockerfile`
   - Document in `docker/README.md`

3. **Resolve curate_epi.py duplication**
   - Keep production version in `data_curation_scripts/epi/`
   - Move or delete sandbox version

4. **Add README files**
   - `config/README.md` - Config registry
   - `tools/README.md` - Tool purposes
   - `scripts/README.md` - Script organization
   - `data_curation_scripts/PIPELINE.md` - Execution order

5. **Create top-level ARCHITECTURE.md**
   - Document intended scope of this repo
   - Clarify relationship with laser-core, laser-polio, laser-polio-calibration
   - Define boundaries: what belongs here vs. in other packages

### Medium-Term

6. **Extract or clearly isolate response_sia_sweep**
   - Decision needed: extract to separate package OR keep as tool?
   - If keeping: add comprehensive README and treat as sub-project
   - If extracting: create `laser-polio-response-sweep` package

7. **Audit and clean legacy code**
   - Review `scripts/legacy/` (after reorganization)
   - Delete clearly obsolete code
   - Archive important exploratory work with documentation

8. **Consolidate plotting utilities**
   - Decide: should plots be in `tools/` or `scripts/analysis/`?
   - Move all exploratory plots to `scripts/analysis/`
   - Keep only production-ready utilities in `tools/`

9. **Add data curation pipeline orchestration**
   - Create `data_curation_scripts/run_all.py` orchestrator
   - Document dependencies and execution order
   - Add validation checks between stages

### Long-Term (Architectural)

10. **Consider package split options:**

**Option A: Minimize this repo**
```
laser-polio-nigeria/
├── config/              # Nigeria-specific configs only
├── src/                 # Thin wrappers only
└── examples/            # Demos only

# Move elsewhere:
- data_curation → laser-polio-data-tools (shared package)
- response_sia_sweep → laser-polio-response-sweep
- tools → laser-polio-analysis-tools (shared package)
```

**Option B: Make this the Nigeria hub**
```
laser-polio-nigeria/
├── config/              # All Nigeria configs
├── src/                 # Nigeria-specific integration layer
├── pipelines/           # Organized data pipelines (renamed from scripts)
│   ├── data_curation/
│   ├── validation/
│   ├── analysis/
│   └── response_sweep/
├── tools/               # Production utilities only
└── examples/            # Demos
```

**Option C: Split further**
```
laser-polio-nigeria-core       # Configs + thin wrappers
laser-polio-nigeria-tools      # Data curation + analysis
laser-polio-response-sweep     # Sweep infrastructure
```

---

## Organizational Anti-Patterns Summary

1. **Unclear Code Ownership** - Ambiguous boundaries after monolith split
2. **Sandbox as Dumping Ground** - No lifecycle management for exploratory code
3. **Config Sprawl** - No registry or central documentation
4. **Docker Duplication** - Multiple files, unclear canonical version
5. **Mixed Production/Development** - No clear separation
6. **Mini-App Embedded** - Response sweep is large enough to be standalone
7. **Data Pipeline Undocumented** - No dependency graph or execution order
8. **Tools/Scripts Overlap** - Unclear distinction between utilities and exploration

---

## Questions to Guide Next Steps

To prioritize the refactoring, answer these questions:

1. **What is the intended scope of laser-polio-nigeria?**
   - Country-specific configs only?
   - Full Nigeria analysis platform?
   - Integration layer + tools?

2. **Should response_sia_sweep be extracted?**
   - Is it used by other countries/projects?
   - Does it need independent versioning?
   - Could it be a standalone CLI tool?

3. **What's the relationship with laser-polio-calibration?**
   - Should calibration configs live here or there?
   - Is the thin wrapper approach permanent?

4. **Which code is actively maintained?**
   - Is `comps/run.py` (2024 lines) still used?
   - Are all 33 sandbox scripts needed?
   - Which tools are production vs exploratory?

5. **What's the Docker strategy?**
   - Single image for all use cases?
   - Separate images for development vs production?
   - Base image + country-specific layers?

---

## Conclusion

This repository shows clear evidence of active refactoring from a monolithic architecture to modular packages. The Nigeria-specific layer is functional but caught between old and new organizational patterns.

**Key Insight:** The core issue isn't code quality but **unclear boundaries**. Once you decide what belongs in `laser-polio-nigeria` vs. other packages, the organizational structure will become clear.

**Recommended First Step:** Create an `ARCHITECTURE.md` document defining:
- Intended scope of this repo
- Relationship with other laser-* packages
- What types of code belong here vs. elsewhere
- Production vs. development code boundaries

This will guide all other refactoring decisions.
