#!/bin/bash
#SBATCH --ntasks=1
#SBATCH --partition=gpu_a40
#SBATCH --job-name=VBMS
#SBATCH --output=VBMS_stdout.out
#SBATCH --error=VBMS_stderr.err
#SBATCH --mem=2G
#SBATCH --oversubscribe
#SBATCH --time=24:00:00

job_name="$1"
job_path="/home/.../jobs/$job_name"

echo "SLURM Job ID: $SLURM_JOB_ID"
echo "Job Name: $job_name"
echo "Job started at: $(date)"

result_path="/home/..../results/$job_name"
failed_job_path="/home/.../failed_jobs/$job_name"

apptainer run --bind "$job_path:/mounted/" /home/.../physiboss_container/container.sif
exit_code=$?

echo "$job_name,$SLURM_JOB_ID" >> "$job_path/job_info.txt"

if [ $exit_code -eq 0 ]; then
  mv "$job_path" "$result_path"
else
  echo "apptainer run failed!" >&2
  mv "$job_path" "$failed_job_path"
  exit 1
fi