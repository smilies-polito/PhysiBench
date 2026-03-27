# simulations/data_extraction_hpc.py


import argparse
import os
import time
import random
import itertools
import subprocess
import json
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional

import numpy as np

from data_extraction_physiboss import Physiboss, ModelParameters, Protocols
from initial_positions import InitialPosition

# ==================== CONFIG HPC (GLOBAL VARIABLES FROM CLI) ====================
remote_user = None
remote_host = None
remote_base = None
remote_results_path = None
run_script = None

# ==================== SCHEDULING (GLOBAL VARIABLES FROM CLI) ====================
GRID_SIZE       = None
MAX_CONCURRENT  = None
SAVE_TIME       = None
MAX_RETRIES     = None
STALE_MINUTES   = None
base_mount_path = None
INITIAL_POSITIONS_JSON_PATH = None
times_dir = None


# ==================== LISTA MODELLI E INITIAL POSITIONS ====================
INITIAL_POSITIONS: Dict[Tuple[str, str, Optional[str]], InitialPosition] = {}
MODELS: List[Tuple[str, str, Optional[str]]] = []

def parse_model_key(model_key: str) -> Tuple[str, str, Optional[str]]:
    parts = model_key.split("_")
    if len(parts) < 2:
        raise ValueError(f"Invalid model key format: {model_key}")
    if parts[-1].startswith("V"):
        return "_".join(parts[:-1]), parts[-1], None
    if len(parts) < 3 or not parts[-2].startswith("V"):
        raise ValueError(f"Invalid model key format: {model_key}")
    return "_".join(parts[:-2]), parts[-2], parts[-1]

def load_initial_positions(pool_directory):
    global INITIAL_POSITIONS, MODELS
    seen_models = set()
    with open(INITIAL_POSITIONS_JSON_PATH, "r") as f:
        _initial_positions_data = json.load(f)
    for k, v in _initial_positions_data.items():
        name, version, model_id = parse_model_key(k)
        key = (name, version, model_id)
        if key not in seen_models:
            MODELS.append(key)
            seen_models.add(key)
        INITIAL_POSITIONS[key] = InitialPosition(
            type=v["type"],
            center=tuple(v["center"]),
            density=v["density"],
            cell_type=v["cell_type"],
            mode=v["mode"],
            length=v["length"]
        )
    for model in MODELS:
        family, version, _ = model 
        original_path = os.path.join(pool_directory, family)
        destination_dir = os.path.join(base_mount_path, family)
        os.makedirs(destination_dir, exist_ok=True)
        print(f"Copying {original_path}/{version}(.bnd, .cfg) to {destination_dir}/{version}(.bnd, .cfg)")
        os.system(f"cp -r {original_path}/{version}.bnd {destination_dir}/{version}.bnd")
        os.system(f"cp -r {original_path}/{version}.cfg {destination_dir}/{version}.cfg")

SSH_OPTS = [
    "-o", "BatchMode=yes",
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "ServerAliveInterval=30",
    "-o", "ServerAliveCountMax=3",
    "-o", "ConnectTimeout=10",
    # Facoltativo ma consigliato: multiplex per ridurre handshake
    # "-o", "ControlMaster=auto",
    # "-o", "ControlPersist=60s",
    # "-o", "ControlPath=~/.ssh/ctl-%r@%h:%p",
]

# ==================== SIM PARAMS ====================
@dataclass
class SimParams:
    max_time: int = 1700
    domain_size: int = 206
    dt_diffusion: float = 0.256
    dt_mechanics: float = 0.152
    dt_phenotype: float = 5.718
    num_threads: int = 3
    diffusion_coefficient: float = 1070
    speed: float = 3.3
    intracellular_dt: float = 518
    save_time: int = SAVE_TIME  # used by Physiboss to write XML

# ==================== GRID (ASSOLUTA) ====================
def get_values_and_intermediates(start: float, stop: float, num: int):
    lin = np.linspace(start, stop, num)
    mids = [(lin[i] + lin[i+1]) / 2 for i in range(len(lin) - 1)]
    return lin.tolist(), mids

def build_combinations_topN(N: int) -> List[Tuple[float, float, float, float, float, float]]:
    treatment_periods, _   = get_values_and_intermediates(5, 800, 10)  # minutes
    treatment_durations, _ = get_values_and_intermediates(5, 200, 10)  # minutes
    xmins, _               = get_values_and_intermediates(0, 10, 10)
    xmaxs, _               = get_values_and_intermediates(0, 10, 10)
    ymins, _               = get_values_and_intermediates(0, 10, 10)
    ymaxs, _               = get_values_and_intermediates(0, 10, 10)

    combos_raw = list(itertools.product(
        treatment_periods, treatment_durations, xmins, xmaxs, ymins, ymaxs
    ))
    combos = [c for c in combos_raw if c[1] <= c[0]]  # optional filter
    random.shuffle(combos)
    return combos[:N]

# ==================== HPC STATUS HELPERS ====================
def check_remote_status(job_name: str) -> str:
    """
    Returns:
      - "OK"   if results/<job>/finished.ok exists
      - "ERR"  if results/<job>/finished.err exists
      - "NONE" otherwise, or on transient SSH failures/timeouts (so the loop can retry)
    """
    cmd = [
        "ssh", *SSH_OPTS, f"{remote_user}@{remote_host}",
        (
            f"if [ -f {remote_results_path}/{job_name}/finished.ok ]; then echo OK; "
            f"elif [ -f {remote_results_path}/{job_name}/finished.err ]; then echo ERR; "
            f"else echo NONE; fi"
        ),
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=20)
        last = out.decode().strip().splitlines()[-1].strip()
        return last
    except subprocess.TimeoutExpired:
        # Transient: treat as NONE so the outer loop retries later
        return "NONE"
    except subprocess.CalledProcessError:
        # e.g., "Connection closed by host" or nonzero exit -> transient
        return "NONE"
    except Exception:
        # Any other unexpected issue: don't crash the orchestrator
        return "NONE"

# -------------------- CPU TIME HELPERS (no sacct) --------------------
def _times_csv_path(base_model_dir: str) -> str:
    """
    Build the per-model CSV path: <times_dir>/data_extraction_hpc_time_<MODEL>.csv
    MODEL is inferred from base_model_dir basename (e.g., 'macrophage_V2').
    """
    model_tag = os.path.basename(base_model_dir.rstrip("/"))
    os.makedirs(times_dir, exist_ok=True)
    return os.path.join(times_dir, f"data_extraction_hpc_time_{model_tag}.csv")

def _parse_cpu_time_csv(csv_path: str) -> Dict[str, Optional[str]]:
    """
    Parse CPU_time_<SUFFIX>.csv produced on HPC (only timers):
      columns: source,metric,value,unit,notes
    Returns a dict with timers as strings (or None).
    """
    import csv
    out: Dict[str, Optional[str]] = {
        "timers_StepUserSys_sim_s": None,
        "timers_StepUserSys_post_s": None,
        "timers_StepUserSys_total_s": None,
    }
    if not os.path.isfile(csv_path):
        return out

    with open(csv_path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            src = (row.get("source") or "").strip()
            met = (row.get("metric") or "").strip()
            val = (row.get("value") or "").strip()
            if src == "timers":
                if met == "StepUserSys_sim":
                    out["timers_StepUserSys_sim_s"] = val or None
                elif met == "StepUserSys_post":
                    out["timers_StepUserSys_post_s"] = val or None
                elif met == "StepUserSys_total":
                    out["timers_StepUserSys_total_s"] = val or None
    return out

def _append_times_row(times_csv: str, row: Dict[str, Optional[str]]) -> None:
    """
    Append a row to the per-model CSV, creating it with header if missing.
    (Only timers columns, no sacct.)
    """
    import csv
    header = [
        "job_name", "sim_id",
        "timers_StepUserSys_sim_s", "timers_StepUserSys_post_s", "timers_StepUserSys_total_s",
    ]
    file_exists = os.path.isfile(times_csv)
    with open(times_csv, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if not file_exists:
            w.writeheader()
        w.writerow({k: row.get(k) for k in header})

def _update_total_row(times_csv: str) -> None:
    """
    Recompute and (re)write a TOTAL row at the end of the per-model CSV:
    sum numeric timer columns across jobs (ignoring empty/None/'').
    """
    import csv
    if not os.path.isfile(times_csv):
        return

    rows: List[Dict[str, str]] = []
    with open(times_csv, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)

    if not rows:
        return

    # filter out existing TOTAL rows
    rows = [r for r in rows if (r.get("job_name") or "") != "__TOTAL__"]

    def _to_float(s: Optional[str]) -> float:
        try:
            return float(s) if s not in (None, "",) else 0.0
        except Exception:
            return 0.0

    # sum relevant numeric fields (timers only)
    sum_fields = [
        "timers_StepUserSys_sim_s",
        "timers_StepUserSys_post_s",
        "timers_StepUserSys_total_s",
    ]
    totals: Dict[str, str] = {k: "" for k in rows[0].keys()}
    totals["job_name"] = "__TOTAL__"
    totals["sim_id"]   = ""
    for f in sum_fields:
        s = sum(_to_float(r.get(f)) for r in rows)
        totals[f] = f"{s:.3f}"

    # rewrite file with rows + TOTAL at end
    header = list(rows[0].keys())
    with open(times_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)
        w.writerow(totals)

# ==================== FETCH (JSON + TEMPI) ====================
def fetch_jsons(job_name: str, sim_id: int, base_model_dir: str) -> None:
    """
    Download ONLY postprocessed JSONs (and CPU time CSV), then clean remote.
    Rename locally with 'sim_id':
      - cell_data_<sim_id>.json.gz
      - input_parameters_<sim_id>.json
    Also:
      - read CPU_time_*.csv into per-model times CSV
      - delete copied CPU_time_*.csv to save space
    """
    # Local data dirs
    data_dir = os.path.join(base_model_dir, "data")
    cell_dir = os.path.join(data_dir, "cell_data")
    ip_dir   = os.path.join(data_dir, "input_parameters")
    os.makedirs(cell_dir, exist_ok=True)
    os.makedirs(ip_dir,   exist_ok=True)

    # Remote and local temp
    remote_post = f"{remote_results_path}/{job_name}/post_json"
    local_tmp   = os.path.join(base_model_dir, "tmp", job_name, "post_json")
    os.makedirs(local_tmp, exist_ok=True)

    # Ensure remote dir exists (avoid scp failure).
    # On transient SSH failures, wait 60s and retry until success.
    while True:
        try:
            subprocess.run([
                "ssh", *SSH_OPTS, f"{remote_user}@{remote_host}",
                f"test -d {remote_post} || mkdir -p {remote_post}"
            ], check=True)
            break
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"⚠️ ssh failed while preparing {job_name} ({e}). Retry in 60s...")
            time.sleep(60)

    # Copy everything present in post_json.
    # On transient SCP failures, wait 60s and retry until success.
    while True:
        try:
            subprocess.run([
                "scp", "-r",
                f"{remote_user}@{remote_host}:{remote_post}/*",
                local_tmp
            ], check=True)
            break
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"⚠️ scp failed while fetching {job_name} ({e}). Retry in 60s...")
            time.sleep(60)

    # Find files and process
    cell_src = None
    ip_src = None
    cpu_files: List[str] = []

    if os.path.isdir(local_tmp):
        for fname in os.listdir(local_tmp):
            p = os.path.join(local_tmp, fname)
            if fname.endswith(".json.gz") and "cell_data" in fname:
                cell_src = p
            elif fname.endswith(".json") and "input_parameters" in fname:
                ip_src = p
            elif fname.endswith(".csv") and fname.startswith("CPU_time_"):
                cpu_files.append(p)

    # Move JSONs to final locations with sim_id
    if cell_src and os.path.isfile(cell_src):
        dst = os.path.join(cell_dir, f"cell_data_{sim_id}.json.gz")
        os.replace(cell_src, dst)

    if ip_src and os.path.isfile(ip_src):
        dst = os.path.join(ip_dir, f"input_parameters_{sim_id}.json")
        os.replace(ip_src, dst)

    # Parse CPU time CSVs (if any), append to per-model CSV, then delete them
    times_csv_path = _times_csv_path(base_model_dir)
    for cpu_csv in cpu_files:
        metrics = _parse_cpu_time_csv(cpu_csv)
        row = {
            "job_name": job_name,
            "sim_id": str(sim_id),
            **metrics,
        }
        _append_times_row(times_csv_path, row)
        # delete copied CPU_time csv to free space
        try:
            os.remove(cpu_csv)
        except Exception:
            pass

    # Clean local temp (entire job tmp)
    subprocess.run(["rm", "-rf", os.path.join(base_model_dir, "tmp", job_name)], check=False)

    # Clean remote job dir to free space.
    # On transient SSH failures, wait 60s and retry until success.
    while True:
        try:
            subprocess.run([
                "ssh", *SSH_OPTS, f"{remote_user}@{remote_host}",
                f"rm -rf {remote_results_path}/{job_name}"
            ], check=True)
            break
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"⚠️ ssh failed while cleaning remote dir for {job_name} ({e}). Retry in 60s...")
            time.sleep(60)

# ==================== SUBMIT ====================
def submit_one(sim_idx: int,
               combo: Tuple[float, float, float, float, float, float],
               sim_params: SimParams,
               model: ModelParameters,
               model_id: Optional[str],
               base_model_dir: str) -> Tuple[str, int]:
    tp, td, xmin, xmax, ymin, ymax = combo
    key = (model.boolean_family, model.boolean_model, model_id)
    init_pos = INITIAL_POSITIONS.get(key, InitialPosition.get_random())

    protocol = Protocols(
        treatment_duration=td,
        treatment_period=tp,
        xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax,
        initial_positions=init_pos
    )
    model_tag = f"{model.boolean_family}_{model.boolean_model}" if model_id is None else f"{model.boolean_family}_{model.boolean_model}_{model_id}"
    job_name  = f"{model_tag}_sim_{sim_idx}_TP{tp}_TD{td}"
    Physiboss.run_remote_wt_settings(model, protocol, job_name, sim_params,
                                     remote_user, remote_host, remote_base, run_script, base_mount_path)
    return (job_name, sim_idx)

# ==================== RUN (CODA DINAMICA + FAULT TOLERANCE) ====================
def run_for_one_model(boolean_family: str, boolean_model: str, model_id: Optional[str] = None) -> None:
    print(f"\n=== MODEL: {boolean_family}/{boolean_model} ===")
    model = ModelParameters(boolean_family=boolean_family, boolean_model=boolean_model)

    model_tag = f"{boolean_family}_{boolean_model}" if model_id is None else f"{boolean_family}_{boolean_model}_{model_id}"
    base_model_dir = os.path.join(base_mount_path, model_tag) 
    data_dir = os.path.join(base_model_dir, "data")
    os.makedirs(os.path.join(data_dir, "cell_data"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "input_parameters"), exist_ok=True)

    combinations = build_combinations_topN(GRID_SIZE)
    sim_params = SimParams()  # SAVE_TIME in default

    submitted = 0
    completed = 0
    total     = len(combinations)

    # in_flight: job_name -> {sim_id, retries, submitted_at}
    in_flight: Dict[str, Dict] = {}

    def maybe_submit():
        nonlocal submitted
        while submitted < total and len(in_flight) < MAX_CONCURRENT:
            job_name, sim_id = submit_one(submitted, combinations[submitted], sim_params, model, model_id, base_model_dir)
            in_flight[job_name] = {
                "sim_id": sim_id,
                "retries": 0,
                "submitted_at": time.time(),
            }
            submitted += 1
            print(f"➡️ submit {job_name} | running:{len(in_flight)}/{MAX_CONCURRENT} | left:{total-submitted}")

    # First wave
    maybe_submit()

    while completed < total:
        progressed = False

        for job_name in list(in_flight.keys()):
            status = check_remote_status(job_name)
            meta   = in_flight[job_name]
            sim_id = meta["sim_id"]

            if status == "OK":
                fetch_jsons(job_name, sim_id, base_model_dir)
                del in_flight[job_name]
                completed += 1
                progressed = True
                print(f"✅ done {job_name} | running:{len(in_flight)}/{MAX_CONCURRENT} | completed:{completed}/{total}")
                maybe_submit()

            elif status == "ERR":
                if meta["retries"] < MAX_RETRIES:
                    # Remote cleanup and retry
                    subprocess.run([
                        "ssh", f"{remote_user}@{remote_host}",
                        f"rm -rf {remote_results_path}/{job_name}"
                    ], check=False)
                    combo = combinations[sim_id]
                    new_job_name, _ = submit_one(sim_id, combo, sim_params, model, model_id, base_model_dir)
                    del in_flight[job_name]
                    in_flight[new_job_name] = {**meta, "retries": meta["retries"] + 1, "submitted_at": time.time()}
                    print(f"🔁 retry {job_name} -> {new_job_name} (attempt {meta['retries']+1}/{MAX_RETRIES})")
                    progressed = True
                else:
                    # Hard fail: fetch whatever is there (usually nothing) and free slot
                    fetch_jsons(job_name, sim_id, base_model_dir)
                    del in_flight[job_name]
                    completed += 1
                    print(f"❌ failed {job_name} (no more retries) | completed:{completed}/{total}")
                    progressed = True
                    maybe_submit()

            else:  # "NONE"
                if (time.time() - meta["submitted_at"]) > (STALE_MINUTES * 60):
                    if meta["retries"] < MAX_RETRIES:
                        combo = combinations[sim_id]
                        new_job_name, _ = submit_one(sim_id, combo, sim_params, model, model_id, base_model_dir)
                        del in_flight[job_name]
                        in_flight[new_job_name] = {**meta, "retries": meta["retries"] + 1, "submitted_at": time.time()}
                        print(f"🕒 stale → retry {job_name} -> {new_job_name} (attempt {meta['retries']+1}/{MAX_RETRIES})")
                        progressed = True
                    else:
                        # Give up; don't fetch to avoid deleting potentially useful debug residue
                        del in_flight[job_name]
                        completed += 1
                        print(f"⚠️ stale drop {job_name} | completed:{completed}/{total}")
                        progressed = True
                        maybe_submit()

        if not progressed:
            print(f"⏳ running:{len(in_flight)}/{MAX_CONCURRENT} | queued:{total-submitted}")
            time.sleep(15)

    # After finishing this model: recompute TOTAL row in the per-model CSV
    _update_total_row(_times_csv_path(base_model_dir))

    print(f"🎉 Completed {boolean_family}/{boolean_model}. Data in: {data_dir}")

def main():
    for fam, mod, model_id in MODELS:
        run_for_one_model(fam, mod, model_id)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Data extraction HPC")
    parser.add_argument("--remote-user", default="rsmeriglio", help="HPC username")
    parser.add_argument("--remote-host", default="hpc-legionlogin.polito.it", help="HPC hostname")
    parser.add_argument("--remote-base", default="", help="HPC base dir (default: /home/USER/masera/meta_model_rick)")
    parser.add_argument("--remote-results", default="", help="HPC results dir (default: REMOTE_BASE/results)")
    parser.add_argument("--run-script", default="", help="HPC run script path (default: REMOTE_BASE/run_job.sh)")
    parser.add_argument("--grid-size", type=int, default=2000, help="Grid size combinations")
    parser.add_argument("--max-concurrent", type=int, default=100, help="Max parallel jobs")
    parser.add_argument("--save-time", type=int, default=60, help="Save interval (min) written in XML")
    parser.add_argument("--max-retries", type=int, default=1, help="Max retries for failed job")
    parser.add_argument("--stale-minutes", type=int, default=1500, help="Minutes without marker -> stale")
    parser.add_argument("--base-mount-path", default="/mnt", help="Local mount path for results")
    parser.add_argument("--init-pos-json", default=os.path.join(os.path.dirname(__file__), "initial_positions.json"), help="Initial positions JSON")
    parser.add_argument("--input-pool", help="Where to find boolean models")
    parser.add_argument("--times-dir", help="Directory to store times")

    args = parser.parse_args()

    # Apply arguments to global configs
    remote_user = args.remote_user
    remote_host = args.remote_host
    remote_base = args.remote_base or f"/home/{remote_user}/masera/meta_model_rick"
    remote_results_path = args.remote_results or f"{remote_base}/results"
    run_script = args.run_script or f"{remote_base}/run_job.sh"

    GRID_SIZE = args.grid_size
    MAX_CONCURRENT = args.max_concurrent
    SAVE_TIME = args.save_time
    MAX_RETRIES = args.max_retries
    STALE_MINUTES = args.stale_minutes
    base_mount_path = args.base_mount_path
    INITIAL_POSITIONS_JSON_PATH = args.init_pos_json
    times_dir = args.times_dir

    input_directory = args.input_pool
    
    print(
        "Running data extraction from input directory: ", input_directory,
        "\nStoring results in: ", base_mount_path
    )
    load_initial_positions(input_directory)

    # We keep a small global wall/CPU time for the orchestrator itself (not used in per-model CSVs)
    start = time.time()
    main()
    total = time.time() - start

    # Orchestrator timings (optional; not requested in per-model CSVs)
    print(f"\n=== ALL DONE in {total} seconds ===")
    os.makedirs(times_dir, exist_ok=True)
    with open(os.path.join(times_dir, "data_extraction_effective_time.txt"), "w", encoding="utf-8") as f:
        f.write(f"Total wall time: {total:.2f} seconds\n")
