#!/bin/bash
#SBATCH --ntasks=1
#SBATCH --partition=gpu_a40
#SBATCH --job-name=PHYSIBOSS_masera
#SBATCH --output=PHYSIBOSS_masera_stdout.out
#SBATCH --error=PHYSIBOSS_masera_stderr.err
#SBATCH --mem=2G
#SBATCH --oversubscribe
#SBATCH --time=24:00:00
# alternativa nodo: compute-4-12 o 7-2, 7-3

job_name="$1"
job_path="/home/rsmeriglio/masera/jobs/$job_name"

echo "SLURM Job ID: $SLURM_JOB_ID"
echo "Job Name: $job_name"
echo "Job started at: $(date)"

result_path="/home/rsmeriglio/masera/results_new_dir/$job_name"
failed_job_path="/home/rsmeriglio/masera/failed_jobs/$job_name"

apptainer run --bind "$job_path:/mounted/" /home/rsmeriglio/masera/physiboss_container/container.sif
exit_code=$?

echo "$job_name,$SLURM_JOB_ID" >> "$job_path/job_info.txt"

if [ $exit_code -eq 0 ]; then
  mv "$job_path" "$result_path"
else
  echo "apptainer run failed!" >&2
  mv "$job_path" "$failed_job_path"
  exit 1
fi