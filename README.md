# BIDMS: Biological-Inspired Dataset for Multiscale Simulation

In computational biology, the availability of longitudinal data describing dynamical processes is constrained by multiple factors, including the high cost and experimental burden of repeated measurements, as well as the limited availability of accurate and diverse dynamical models for many biological systems. As a consequence, both experimental and synthetic datasets capturing biological dynamics remain scarce, hindering the systematic development, validation, and benchmarking of computational methodologies targeting dynamical biological processes.

The **Biological-Inspired Dataset for Multiscale Simulation (BIDMS)** addresses this limitation by enabling the generation of bio-plausible synthetic dynamical data through a curated collection of 2,115 structurally diverse Boolean regulatory networks designed for multi-scale simulation within the PhysiBoSS framework. These networks are generated via a mutation-based construction pipeline and subsequently filtered to maximise inter-model heterogeneity in dynamical behaviour. This process yields a final subset of 612 Boolean models which, while not corresponding to specific known biological systems, introduce only minimal structural and logical variations from biologically grounded models. As a result, they preserve key topological and dynamical characteristics observed in biological regulatory networks while substantially expanding the available model space, enabling large-scale simulation studies across a broad spectrum of bio-inspired systems and supporting robust benchmarking of computational approaches to biological dynamics.

## Overview

The workflow consists of several key stages:

1. **Base Pool Generation**: Transforms source biological models into a generic base pool
2. **Mutation Pipeline**: Generates diverse model variants through controlled mutations (logic switching, operator replacement, node manipulation, etc.)
3. **Distance Computation**: Calculates graph-based distance metrics (DeltaCon, Ipsen-Mikhailov, QuantumJSD) to quantify model diversity
4. **Sensitivity Analysis**: Performs systematic sampling across different biological contexts and subjects
5. **Model Filtering**: Applies statistical thresholds to select high-quality models for downstream analysis

## Setup Environment

The simplest way to setup the execution environment is through Singularity, although building from source code is also possible.

### Option 1: Singularity container

**Requirements**: Singularity.

Build and use the provided container:
```bash
make container.sif
```

Open a shell inside the container and activate the conda environment:
```bash
make open_shell
conda activate bidms
cd snakemake_workflow
```

Note: when working inside Singularity, the directories physiboss/config_template and physiboss/virtualoutput are mounted inside the container and used to set the simulation parameters and retrieve the outputs.

### Option 2: Local Installation

**Requirements**
- Conda
- GCC compiler


1. Build PhysiBoSS:
   ```bash
   cd src/bin/physiboss/Physiboss
   make
   ```

2. Install the conda environment:
   ```bash
   conda env create -f workflow/env/env.yml
   conda activate <env-name>
   ```


### Option 2: Singularity Container (Recommended for HPC)

Build and use the pre-configured container for reproducible execution:
```bash
singularity build container.sif singularity_def/container.def
singularity shell container.sif
```

## Usage

This project follows the standard Snakemake workflow structure. The pipeline logic is distributed across:

- **`workflow/Snakefile`**: Main workflow orchestration and final outputs
- **`workflow/rules/boolean_models_mutations.smk`**: Rules for model generation and mutation
- **`workflow/rules/boolean_models_filtering.smk`**: Rules for sampling and filtering
- **`config/config.yaml`**: All configurable parameters and thresholds

### Configuration

Edit `config/config.yaml` to customize:
- Source model directories and output paths
- Number of models to generate (`target_number_of_models`)
- Mutation probabilities and constraints
- Distance computation parameters
- Sampling strategy (contexts, subjects)
- Filtering thresholds (mean, standard deviation)
- Remote execution settings (optional)

### Running the Workflow

Navigate to the workflow directory:
```bash
cd snakemake_workflow
```

**Dry run** to preview execution plan:
```bash
snakemake -n
```

**Execute the full pipeline**:
```bash
snakemake --cores <n>
```

**Use conda environments automatically**:
```bash
snakemake --use-conda --cores <n>
```

**Generate only specific outputs**:
```bash
# Generate mutated models and compute distances only
snakemake results/boolean_models/static_distance --cores <n>

# Run complete pipeline including filtering
snakemake results/filtering --cores <n>
```

### Remote Execution (Optional)

For computationally intensive tasks, the workflow supports remote execution on HPC systems. Configure the following parameters in `config/config.yaml`:

```yaml
use_remote: true
remote_url: "user@hpc-server.domain"
remote_results_path: "/home/user/results"
remote_failed_path: "/home/user/failed"
remote_temp_path: "/home/user/temp"
```
