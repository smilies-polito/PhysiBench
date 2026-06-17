#!/bin/bash
#SBATCH --ntasks=1
#SBATCH --partition=gpu_a40
#SBATCH --job-name=PhysiBench
#SBATCH --time=24:00:00
#SBATCH --mem=2G
#SBATCH --chdir=/home/<..>
#SBATCH --output=/home/<..>
#SBATCH --error=/home/<..>

set -euo pipefail

base="/home/" # Please setup
job_name="${1:?Usage: run_job.sh <job_name> [suffix]}"
SUFFIX="${2:-SIM}"  # opzionale, default SIM

job_path="$base/jobs/$job_name"
result_path="$base/results/$job_name"

SIM_CONTAINER="$base/container.sif"
PY_CONTAINER=$SIM_CONTAINER # Can use the same container as long as it has python3 and the XML library

TIME_SIM_TXT="$job_path/.time_sim.txt"
TIME_POST_TXT="$job_path/.time_post.txt"

PYTHON_TOOLS_PATH="$base/tools"

job_completed=0

if command -v apptainer >/dev/null 2>&1; then
  CONTAINER_RUNTIME="apptainer"
elif command -v singularity >/dev/null 2>&1; then
  CONTAINER_RUNTIME="singularity"
else
  echo "ERROR: neither apptainer nor singularity is available on this node." >&2
  exit 127
fi

write_external_failure_marker() {
  local ec="${1:-1}"
  local reason="${2:-Job aborted before managed failure handling}"
  if [[ "$job_completed" -eq 1 ]]; then
    return
  fi
  if [[ -f "$result_path/finished.ok" || -f "$result_path/finished.err" ]]; then
    return
  fi
  mkdir -p "$result_path" 2>/dev/null || true
  {
    echo "exit_code=$ec"
    echo "$reason"
  } > "$result_path/finished.err" 2>/dev/null || true
}

on_exit() {
  local ec=$?
  if [[ $ec -ne 0 ]]; then
    write_external_failure_marker "$ec" "Job aborted before managed failure handling"
  fi
}

on_term() {
  write_external_failure_marker 143 "Job terminated by external signal"
  exit 143
}

trap on_exit EXIT
trap on_term TERM INT

mkdir -p "$base/results" "$base/slurm_logs_new"

echo "===> START $(date)"
echo "Job: $job_name"
echo "job_path=$job_path"
echo "result_path=$result_path"
echo "suffix=$SUFFIX"
echo "container_runtime=$CONTAINER_RUNTIME"

# --- SIMULAZIONE (CPU time: user+sys) ---
mkdir -p "$job_path/post_json"
if ! ( TIMEFORMAT=$'user=%U\nsys=%S\nelapsed=%E'
       { time "$CONTAINER_RUNTIME" exec --cleanenv --bind "$job_path:/mounted" \
             "$SIM_CONTAINER" bash -lc 'cd /opt/PhysiCell && ./project' \
             > "$job_path/container_stdout.log" 2> "$job_path/container_stderr.log"; } \
       2> "$TIME_SIM_TXT"
     )
then
  ec=$?
  mkdir -p "$result_path"
  echo "$job_name,$SLURM_JOB_ID,$ec" >> "$job_path/job_info.txt" || true
  cp -r "$job_path"/{config,output,job_info.txt} "$result_path/" 2>/dev/null || true
  echo "exit_code=$ec" > "$result_path/finished.err"
  echo "Simulation failed" >> "$result_path/finished.err"

  # genera comunque CSV con tempi CPU
  python3 "$PYTHON_TOOLS_PATH/postprocess_time.py" \
    --job-dir "$job_path" \
    --suffix "$SUFFIX" \
    --time-sim "$TIME_SIM_TXT" \
    --time-post "$TIME_POST_TXT" || true

  mkdir -p "$result_path/post_json"
  cp -r "$job_path/post_json/"* "$result_path/post_json/" 2>/dev/null || true
  cp -r "$job_path/config/PhysiCell_settings.xml" "$result_path/" 2>/dev/null || true
  exit 0
fi

echo "$job_name,$SLURM_JOB_ID,0" >> "$job_path/job_info.txt"

# --- POSTPROCESS (CPU time: user+sys) ---
if ! ( TIMEFORMAT=$'user=%U\nsys=%S\nelapsed=%E'
       { time "$CONTAINER_RUNTIME" exec --cleanenv --bind "$job_path:/mounted" \
             "$PY_CONTAINER" python3 "$PYTHON_TOOLS_PATH/postprocess.py" \
             --job-dir "/mounted" --suffix "$SUFFIX"; } \
       2> "$TIME_POST_TXT"
     )
then
  ec=$?
  mkdir -p "$result_path"
  cp -r "$job_path"/{post_json,config,output,job_info.txt} "$result_path/" 2>/dev/null || true
  echo "exit_code=$ec" > "$result_path/finished.err"
  echo "Postprocess failed" >> "$result_path/finished.err"

  python3 "$PYTHON_TOOLS_PATH/postprocess_time.py" \
    --job-dir "$job_path" \
    --suffix "$SUFFIX" \
    --time-sim "$TIME_SIM_TXT" \
    --time-post "$TIME_POST_TXT" || true

  mkdir -p "$result_path/post_json"
  cp -r "$job_path/post_json/"* "$result_path/post_json/" 2>/dev/null || true
  cp -r "$job_path/config/PhysiCell_settings.xml" "$result_path/" 2>/dev/null || true
  exit 0
fi

# --- CSV finale con soli tempi CPU (user+sys) ---
python3 "$PYTHON_TOOLS_PATH/postprocess_time.py" \
  --job-dir "$job_path" \
  --suffix "$SUFFIX" \
  --time-sim "$TIME_SIM_TXT" \
  --time-post "$TIME_POST_TXT" || true

# --- CONSEGNA RISULTATI LEGGERI ---
mkdir -p "$result_path/post_json"
cp -r "$job_path/post_json/"* "$result_path/post_json/" 2>/dev/null || true
cp -r "$job_path/config/PhysiCell_settings.xml" "$result_path/" 2>/dev/null || true

# --- PULIZIA ---
#rm -rf "$job_path/output" "$job_path/config" 2>/dev/null || true
rm -f "$TIME_SIM_TXT" "$TIME_POST_TXT" 2>/dev/null || true

# --- MARKER OK ---
mv "$job_path" "$result_path/.work" 2>/dev/null || true
mv "$result_path/.work" "$result_path" 2>/dev/null || true
job_completed=1
trap - EXIT TERM INT
touch "$result_path/finished.ok"

echo "===> DONE $(date)"