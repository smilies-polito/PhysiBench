# VBMS: Variant Boolean Models and Multiscale Simulations

The development of computational methodologies for analyzing biological dynamics is constrained by the limited availability and complexity of time-resolved datasets. Acquiring longitudinal data is costly, and its downstream use is often complicated by missing observations or irregular sampling. While large-scale simulation benchmark datasets exist for physical systems, they do not capture the emergent, stochastic, and hybrid multiscale nature of biological biology. 

**VBMS (Variant Boolean Models and Multiscale Simulations)** addresses this gap by providing a curated dataset of simulation-ready intracellular models embedded in a uniform multiscale framework. Designed to accelerate data-driven method development, surrogate modeling, and comparative benchmarking, this resource allows researchers to generate, compare, and analyze multiscale biological simulations under consistent conditions.

Derived from seven open biological reference models, the dataset features:
* **612 variant MaBoSS Boolean regulatory networks:** Filtered from a mutation-based pipeline of 2,122 candidate networks to maximize structural and dynamical diversity. All models are provided with the code required for direct execution within the shared PhysiBoSS/PhysiCell framework.
* **120,000 precomputed time-resolved trajectories:** Generated from 60 representative models under multiple stimulation parameterizations and environmental conditions, dramatically lowering the computational barrier to immediate reuse.

By coupling diverse intracellular Boolean networks with a consistent agent-based multicellular environment, VBMS retains key biological features—such as nonlinearity, stochasticity, feedback, and multiscale coupling—enabling robust, large-scale studies across a broad spectrum of bio-inspired systems.

## Overview

The workflow consists of several key stages designed to generate and validate a structurally diverse dataset of Boolean models and their multiscale simulations:

1. **Base Pool Generation** (rule `base_pool`): Transforms the source biological reference models into a harmonized set of generic Boolean networks. Each model is equipped with a minimal, consistent interface comprising one input node and three output nodes to enable interoperable multiscale simulations.

2. **Mutation Pipeline & On-line Evaluation** (rule `pool`): Applies a stochastic mutation-and-selection process to the base models to create structurally diverse candidate networks. Mutations alter network topology and update rules, such as rewiring logic, replacing operators, and adding nodes. Candidate models are filtered dynamically during generation using a behavioral signature distance threshold to prevent dynamic redundancy.

3. **Sensitivity Analysis & Sampling** (rule `sampling`): Conducts an off-line sensitivity evaluation by simulating the variant models across hundreds of biological contexts. This step uses the PhysiBoSS multiscale framework to evaluate each model under distinct combinations of stimulation and spatial parameters.

4. **Model Filtering** (rule `filtering`): Discards weakly informative models by analyzing their population-level fitness responses across the sampled parameter space. Models are retained only if they demonstrate sufficient absolute and relative variability, evaluated via standard deviation and coefficient of variation thresholds.

5. **Static Distance Validation** (rule `static_distances`): Quantifies the true structural diversity of the curated model collection by converting the Boolean rules into graph representations. It calculates pairwise global distance metrics—DeltaCon, Ipsen-Mikhailov, and Quantum Jensen-Shannon Divergence—to ensure topological distinction.

6. **Multiscale Simulation Extraction** (rule `data_extraction_hpc`): Executes the final, large-scale dataset generation across High-Performance Computing (HPC) resources. It runs a massive grid of parameterizations to extract and save precomputed, time-resolved simulation trajectories for downstream analysis.

## Usage

This project follows the standard Snakemake workflow structure, organizing configurations, rules, and scripts into dedicated directories. 

All workflow executions should be run from the root of the Snakemake pipeline, which is located in `src/dataset_generation`. 

### Project Structure

The repository is organized as follows:

```text
.
├── data/
│   ├── reference_models/       # Initial reference models to mutate
│   ├── boolean_models/
│   │   ├── base_pool/          # Reference models made generic and ready for mutations
│   │   ├── mutated/            # Generated mutated models
│   │   └── filtered/           # Generated mutated models after offline filtering
│   └── multiscale_simulations/ # Results of the multi-scale simulations
├── results/
│   ├── sampling/               # Raw data (sensitivity analysis)
│   ├── filtering/              # Statistics for the sampling step (sensitivity analysis)
│   └── static_distances/       # Raw results and plots for the static distance measures
├── singularity/
│   └── container.def           # Definition file to build the Singularity container
└── src/
    ├── bin/
    │   └── physiboss/          # PhysiBoss executables and source
    └── dataset_generation/     # Root directory to run the Snakemake pipeline
        ├── config/
        │   └── config.yaml     # All configurable hyperparameters and remote settings
        └── workflow/
            ├── env/
            │   └── env.yaml    # Conda environment definition
            ├── rules/          # Directory containing all Snakemake rules (.smk)
            ├── scripts/        # Python scripts called by the rules
            └── Snakefile       # Main Snakemake orchestration file
```

### Environment Setup
You can set up the environment in two ways: using a **Singularity container** (recommended) or **manually via Conda**.

#### Using Singularity (Recommended)
A Makefile is provided in the root directory to easily build and launch the container with the correct volume bindings.

To build the container (container.sif):

```bash
make container.sif
```

```bash
To launch the interactive shell inside the container:
```

```bash
make launch_container
```
Note: This automatically binds the necessary PhysiCell configuration directories and your current working directory.

#### Manual Setup (Conda)
If you prefer not to use Singularity, you can recreate the environment using the provided YAML file:

```bash
conda env create -f src/dataset_generation/workflow/env/env.yaml
conda activate <env_name>
```

### Configuration
All hyperparameters and pipeline settings are centralized in src/dataset_generation/config/config.yaml. This file dictates the behavior of the entire workflow. 
The specific hyperparameters of individual steps of the pipeline will be documented below.

### Running the Workflow
To execute the pipeline, first navigate to the workflow root directory:

```bash
cd src/dataset_generation
snakemake -j<n> all
```

Here are some common Snakemake commands to run the workflow:

Dry run (preview the execution plan without running anything):
```bash
snakemake -n
```

Execute the full pipeline locally using <n> cores:
```bash
snakemake --cores <n>
```

### Remote Execution (HPC)
For computationally intensive tasks (like sampling, filtering, and data extraction), the workflow natively supports remote execution on HPC systems.

You can configure this by editing the dedicated HPC sections in config.yaml. An example submission script (run_job.sh) is available in the root directory.

Standard HPC execution fields:

YAML
# Remote execution settings
use_remote: false           # Set to true to enable HPC for the sampling/filtering step
remote_user: "rsmeriglio"   # Remote user on HPC
remote_host: "hpc-legionlogin.polito.it" # Host address on HPC
remote_url: "rsmeriglio@hpc-legionlogin.polito.it" # Combination of user and host
remote_results_path: "/home/rsmeriglio/masera/results_new_dir" # Where HPC stores results
remote_failed_path: "/home/rsmeriglio/masera/failed_jobs"      # Where HPC stores failed jobs
remote_temp_path: "/home/rsmeriglio/masera/jobs"               # Temp dir on the HPC where jobs are sent
hpc_script_name: "masera/run_job.sh"                           # Script on the HPC to launch jobs
max_jobs_stop: 480          # Threshold to stop sending new jobs
max_jobs_resume: 210        # Threshold to resume sending new jobs
Data Extraction HPC fields:

YAML
# Remote execution settings for the data extraction step
extraction_remote_base: "/home/rsmeriglio/masera/meta_model_rick"           # Base directory on the HPC
extraction_remote_results: "/home/rsmeriglio/masera/meta_model_rick/results" # Directory for extraction results
extraction_remote_script: "/home/rsmeriglio/masera/meta_model_rick/run_job.sh" # Remote script for this specific task


TODO:
 - Step della pipeline: per ogni step:
    - Descrizione leggermente più lunga.
    - quali directory di input si usano e quali directory di output si popolano.
    - Spiegazione degli iperparametri (tutti appartengono al config.yaml).