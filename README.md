# BIDMS

This repository provides a workflow for generating synthetic datasets for the PhysiBoSS simulator by applying systematic mutations to a pool of biological models. The generated datasets can be used for training machine learning models, testing simulation pipelines, or performing sensitivity analyses on biological model parameters.

## Setup Environment

### Requirements
- Conda
- GCC compiler

### Option 1: Local Installation

1. Build PhysiBoSS:
   ```bash
   cd physiboss/Physiboss
   make
   ```

2. Install the conda environment:
   ```bash
   conda env create -f workflow/env/env.yml
   conda activate <env-name>
   ```

### Option 2: Singularity Container

Build and use the provided container:
```bash
make container.sif
```

Open a shell inside the container:
```bash
make open_shell
conda activate bidms
cd snakemake_workflow
```

## Usage

This is a standard Snakemake workflow. The pipeline is defined across multiple files:
- `Snakefile`: Main workflow orchestration
- `*.smk` files: Additional workflow rules
- `config.yml`: Configuration parameters

### Running the Workflow

Execute from the workflow directory:
```bash
cd snakemake_workflow
snakemake --cores <n>
```

For a dry run to see what will be executed:
```bash
snakemake -n
```

To use the conda environment automatically:
```bash
snakemake --use-conda --cores <n>
```

User: Please write in the README.md. Also, write it more thoughfully

GitHub Copilot: # Synthetic Dataset Generator for PhysiBoSS

This repository implements an automated workflow for generating synthetic datasets tailored to the PhysiBoSS simulator. The pipeline systematically applies controlled mutations to a collection of baseline biological models, creating diverse variants that maintain biological plausibility while exploring the parameter space. The resulting datasets enable comprehensive testing of simulation pipelines, training of machine learning models, and execution of large-scale sensitivity analyses on biological model parameters.

## Overview

The workflow consists of several key stages:

1. **Base Pool Generation**: Transforms source biological models into a generic base pool
2. **Mutation Pipeline**: Generates diverse model variants through controlled mutations (logic switching, operator replacement, node manipulation, etc.)
3. **Distance Computation**: Calculates graph-based distance metrics (DeltaCon, Ipsen-Mikhailov, QuantumJSD) to quantify model diversity
4. **Sensitivity Analysis**: Performs systematic sampling across different biological contexts and subjects
5. **Model Filtering**: Applies statistical thresholds to select high-quality models for downstream analysis

## Setup Environment

### Requirements
- **Conda**: For Python environment management
- **GCC**: For compiling PhysiBoSS simulator

### Option 1: Local Installation

1. **Build PhysiBoSS simulator**:
   ```bash
   cd physiboss/Physiboss
   make
   ```

2. **Create and activate the conda environment**:
   ```bash
   conda env create -f workflow/env/env.yml
   conda activate <environment-name>
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
